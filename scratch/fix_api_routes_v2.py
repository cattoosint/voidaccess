import os
import re

dir_path = r'c:\void.access\voidaccess\web\app\api'

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Normalize signatures involving _request or other names
    # Match: export async function METHOD( _request: Request, { params }: ... ) {
    content = re.sub(
        r'export\s+async\s+function\s+(GET|POST|PUT|DELETE)\s*\(\s*[_a-zA-Z0-9]+\s*:\s*Request\s*,\s*\{\s*params\s*\}\s*:\s*\{\s*params\s*:\s*\{\s*([a-zA-Z0-9_]+)\s*:\s*string\s*\}\s*\}\s*\)',
        r'export async function \1(request: Request, { params }: { params: { \2: string } })',
        content
    )
    
    # Match: export async function METHOD( _request: Request ) {
    content = re.sub(
        r'export\s+async\s+function\s+(GET|POST|PUT|DELETE)\s*\(\s*[_a-zA-Z0-9]+\s*:\s*Request\s*\)',
        r'export async function \1(request: Request)',
        content
    )

    # 2. Extract authorization token at the start of the function body
    # We first remove ALL existing token extraction lines to avoid duplicates
    content = re.sub(r'const\s+token\s*=\s*request\.headers\.get\("Authorization"\);?\n?', '', content)
    content = re.sub(r'const\s+token\s*=\s*_request\.headers\.get\("Authorization"\);?\n?', '', content)
    
    # Now insert it right after the function opening brace
    # Match the normalized signature followed by {
    content = re.sub(
        r'(export\s+async\s+function\s+(?:GET|POST|PUT|DELETE)\s*\(.*?\)\s*\{)',
        r'\1\n  const token = request.headers.get("Authorization");',
        content
    )

    # 3. Final cleanup of any _request remainders
    content = content.replace('_request.headers', 'request.headers')

    if content != content: # This logic is wrong in my check, but I'll check against original
        pass

    # To be safe, I'll just write if it changed
    return content

for root, dirs, files in os.walk(dir_path):
    for file in files:
        if file.endswith('.ts') or file.endswith('.tsx'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                old_content = f.read()
            
            new_content = fix_file(filepath)
            
            if new_content != old_content:
                print(f'Fixed {filepath}')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
