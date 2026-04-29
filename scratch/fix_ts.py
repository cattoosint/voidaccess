import os
import re

dir_path = r'c:\void.access\voidaccess\web\app\api'
signature_pattern = re.compile(
    r'export\s+async\s+function\s+(GET|POST|PUT|DELETE)\s*\(\s*request:\s*Request,\s*\{\s*const token = request\.headers\.get\(\"Authorization\"\);\s*params\s*\}:\s*\{\s*params:\s*\{\s*([a-zA-Z0-9_]+):\s*string\s*\}\s*\}\s*\)\s*\{',
    re.DOTALL
)

def replace_func(m):
    method = m.group(1)
    param_name = m.group(2)
    return f'export async function {method}(\n  request: Request,\n  {{ params }}: {{ params: {{ {param_name}: string }} }}\n) {{\n  const token = request.headers.get("Authorization");'

for root, dirs, files in os.walk(dir_path):
    for file in files:
        if file.endswith('.ts'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            new_content = signature_pattern.sub(replace_func, content)
            
            if new_content != content:
                print(f'Fixed {filepath}')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
