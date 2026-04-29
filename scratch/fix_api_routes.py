import os
import re

dir_path = r'c:\void.access\voidaccess\web\app\api'

# Pattern 1: Catch-all for misnamed request parameter or mangled token extraction
# This handles the case where _request: Request is used, or where the token extraction is inside the signature
# Signature: GET|POST( [any_param]: Request, { params }: { params: { dynamic_id: string } } ) {
signature_pattern_dynamic = re.compile(
    r'export\s+async\s+function\s+(GET|POST|PUT|DELETE)\s*\(\s*([_a-zA-Z0-9]+):\s*Request,\s*(\{\s*.*?\s*params\s*\}:\s*\{\s*params:\s*\{\s*([a-zA-Z0-9_]+):\s*string\s*\}\s*\})\s*\)\s*\{',
    re.DOTALL
)

# Pattern 2: For routes with NO dynamic params
signature_pattern_static = re.compile(
    r'export\s+async\s+function\s+(GET|POST|PUT|DELETE)\s*\(\s*([_a-zA-Z0-9]+):\s*Request\s*\)\s*\{',
    re.DOTALL
)

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Step 1: Fix signatures with dynamic params
    def repl_dynamic(m):
        method = m.group(1)
        # We enforce 'request' as the name
        param_name = m.group(4)
        return f'export async function {method}(\n  request: Request,\n  {{ params }}: {{ params: {{ {param_name}: string }} }}\n) {{\n  const token = request.headers.get("Authorization");'

    new_content = signature_pattern_dynamic.sub(repl_dynamic, content)

    # Step 2: Fix signatures with static params
    def repl_static(m):
        method = m.group(1)
        return f'export async function {method}(request: Request) {{\n  const token = request.headers.get("Authorization");'

    new_content = signature_pattern_static.sub(repl_static, new_content)

    # Step 3: Cleanup redundant token extractions if we just inserted one
    # If the file already had 'const token = ...' after we inserted one, it might be duplicated.
    # We'll normalize lines.
    lines = new_content.splitlines()
    final_lines = []
    seen_token_line = False
    for line in lines:
        if 'const token = request.headers.get("Authorization");' in line:
            if seen_token_line:
                continue # Skip duplicate
            seen_token_line = True
        
        # Also fix any leftovers that still use _request
        line = line.replace('_request.headers', 'request.headers')
        line = line.replace('_request', 'request') # Careful here, but in API routes it's safe
        
        final_lines.append(line)
    
    new_content = '\n'.join(final_lines)

    if new_content != content:
        print(f'Fixed {filepath}')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

for root, dirs, files in os.walk(dir_path):
    for file in files:
        if file.endswith('.ts') or file.endswith('.tsx'):
            fix_file(os.path.join(root, file))
