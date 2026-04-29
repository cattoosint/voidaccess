import os
import re

# List of all proxy routes that need Authorization header forwarding
files = [
    r"web\app\api\entities\[id]\export\route.ts",
    r"web\app\api\entities\[id]\related\route.ts",
    r"web\app\api\export\[id]\misp\route.ts",
    r"web\app\api\export\[id]\misp\selected\route.ts",
    r"web\app\api\export\[id]\sigma\route.ts",
    r"web\app\api\export\[id]\stix\route.ts",
    r"web\app\api\export\[id]\stix\selected\route.ts",
    r"web\app\api\investigate\route.ts",
    r"web\app\api\investigations\[id]\route.ts",
    r"web\app\api\investigations\[id]\analysis\temporal\route.ts",
    r"web\app\api\investigations\[id]\entities\route.ts",
    r"web\app\api\investigations\[id]\graph\route.ts",
    r"web\app\api\monitors\alerts\count\route.ts",
    r"web\app\api\monitors\[name]\alerts\route.ts",
    r"web\app\api\monitors\[name]\alerts\acknowledge\route.ts",
]

base_dir = r"c:\void.access\voidaccess"

for rel_path in files:
    abs_path = os.path.join(base_dir, rel_path)
    if not os.path.exists(abs_path):
        print(f"Skipping {abs_path} (not found)")
        continue
    
    with open(abs_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already updated
    if 'request.headers.get("Authorization")' in content or '_request.headers.get("Authorization")' in content:
        print(f"Skipping {rel_path} (already updated)")
        continue

    # Find the function argument name (usually _request or request)
    func_match = re.search(r'export async function (?:GET|POST|PUT|PATCH|DELETE)\s*\(\s*(_?request): Request', content)
    if not func_match:
        print(f"Skipping {rel_path} (could not find request arg)")
        continue
    
    req_arg = func_match.group(1)
    
    # Inject token retrieval
    # For GET requests with {params}:
    # export async function GET(_request: Request, { params }: { params: { id: string } }) {
    #   const { id } = params;
    #   const token = _request.headers.get("Authorization");
    # ...
    
    # Find where to inject 'const token = ...'
    # It should be at the start of the function body.
    body_start_match = re.search(r'\{', content)
    if not body_start_match:
        continue
    
    # Let's find the start of the first function body
    first_brace = content.find('{')
    if first_brace == -1: continue
    
    # Actually, let's just insert it after the function signature line
    sig_match = re.search(r'export async function (?:GET|POST|PUT|PATCH|DELETE).*?\{', content, re.DOTALL)
    if not sig_match: continue
    
    insert_pos = sig_match.end()
    token_line = f'\n  const token = {req_arg}.headers.get("Authorization");'
    
    new_content = content[:insert_pos] + token_line + content[insert_pos:]
    
    # Now find the fetch call and inject headers
    # fetch(`${getBackendUrl()}/...`, {
    #   cache: "no-store",
    # })
    
    fetch_pattern = re.compile(r'fetch\s*\((.*?),\s*\{(.*?)\}\s*\)', re.DOTALL)
    
    def fetch_replacer(match):
        url_part = match.group(1)
        options_part = match.group(2)
        
        # Check if headers already exist
        if 'headers' in options_part:
            # Injecting into existing headers is tricky, but let's assume they are simple objects
            # headers: { "Content-Type": "application/json" }
            headers_match = re.search(r'headers:\s*\{(.*?)\}', options_part, re.DOTALL)
            if headers_match:
                inner_headers = headers_match.group(1)
                new_inner = inner_headers.strip()
                if new_inner and not new_inner.endswith(','):
                    new_inner += ','
                new_inner += '\n          ...(token ? { "Authorization": token } : {})'
                new_options = options_part.replace(inner_headers, f' {new_inner} ')
                return f'fetch({url_part}, {{{new_options}}})'
            else:
                return match.group(0) # Should not happen if matched
        else:
            # Add headers block
            new_options = options_part.strip()
            if new_options and not new_options.endswith(','):
                new_options += ','
            new_options += '\n      headers: {\n        ...(token ? { "Authorization": token } : {})\n      }'
            return f'fetch({url_part}, {{{new_options}}})'

    updated_content = fetch_pattern.sub(fetch_replacer, new_content)
    
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print(f"Updated {rel_path}")
