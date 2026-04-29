import os
import re

files = [
    r"web\app\api\export\[id]\misp\route.ts",
    r"web\app\api\export\[id]\misp\selected\route.ts",
    r"web\app\api\export\[id]\sigma\route.ts",
    r"web\app\api\export\[id]\stix\route.ts",
    r"web\app\api\export\[id]\stix\selected\route.ts",
    r"web\app\api\investigations\[id]\route.ts",
    r"web\app\api\investigations\[id]\analysis\temporal\route.ts",
    r"web\app\api\investigations\[id]\entities\route.ts",
    r"web\app\api\investigations\[id]\graph\route.ts",
    r"web\app\api\entities\[id]\related\route.ts",
]

base_dir = r"c:\void.access\voidaccess"

for rel_path in files:
    abs_path = os.path.join(base_dir, rel_path)
    if not os.path.exists(abs_path):
        continue
    
    with open(abs_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the broken pattern
    #   {
    #   const token = _request.headers.get("Authorization"); params }: { params: { id: string } }
    # ) {
    
    broken_match = re.search(r'\{\s+const token = (_?request)\.headers\.get\("Authorization"\); (params \}: \{ params: \{ id: string \} \})', content)
    if broken_match:
        req_arg = broken_match.group(1)
        params_part = broken_match.group(2)
        
        replacement = f'{{ {params_part} \n) {{\n  const token = {req_arg}.headers.get("Authorization");'
        
        # We also need to remove the extra ') {' that might have stayed
        # Wait, the script inserted AFTER the signature match.
        # Let's just reconstruct the whole function header properly.
        
        # Find the start of the function
        header_start = content.find('export async function GET(')
        if header_start == -1:
            header_start = content.find('export async function POST(')
        
        if header_start != -1:
            # Find the end of the signature ) {
            sig_end = content.find(') {', header_start)
            if sig_end != -1:
                # Reconstruct
                # export async function GET(_request: Request, { params }: { params: { id: string } }) {
                #   const token = _request.headers.get("Authorization");
                
                # Check if it has 'params'
                has_params = 'params' in content[header_start:sig_end+3]
                
                new_sig = f'export async function GET(\n  {req_arg}: Request'
                if has_params:
                    new_sig += ',\n  { params }: { params: { id: string } }'
                new_sig += '\n) {\n  const token = {req_arg}.headers.get("Authorization");'.replace('{req_arg}', req_arg)
                
                # Replace from header_start to whatever the script messed up
                # The script inserted after the MESSED UP sig_end.
                # This is tricky. Let's just use string replace on the known broken part.
                
    # Actually, simpler:
    content = content.replace('{\n  const token = _request.headers.get("Authorization"); params }', '{ params }')
    content = content.replace('{\n  const token = request.headers.get("Authorization"); params }', '{ params }')
    
    # And then make sure token is inside the body
    if ') {' in content:
        pos = content.find(') {') + 3
        if 'const token =' not in content[pos:pos+100]:
            content = content[:pos] + '\n  const token = _request.headers.get("Authorization");' + content[pos:]
            # handle 'request' vs '_request'
            if 'export async function GET(request: Request' in content:
                 content = content.replace('const token = _request', 'const token = request')

    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed {rel_path}")
