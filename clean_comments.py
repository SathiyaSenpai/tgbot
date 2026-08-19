import os
import ast
import re

AI_VERBS = {
    'Initialize', 'Check', 'Log', 'Close', 'Validate', 'Build', 'Register',
    'Start', 'Ensure', 'Create', 'Extract', 'Parse', 'Update', 'Delete',
    'Remove', 'Calculate', 'Format', 'Apply', 'Try', 'Fire', 'Assuming',
    'Send', 'Track', 'Unmute', 'Save', 'Output', 'Get', 'Set', 'Fetch',
    'Handle', 'Find', 'Skip', 'Add', 'Schedule', 'Run', 'Return', 'Count',
    'Replace', 'We', 'In'
}

def is_ai_comment(line):
    line = line.strip()
    if not line.startswith('#'):
        return False
    
    content = line[1:].strip()
    
    # Keep special comments
    if content.startswith('TODO') or content.startswith('FIXME') or content.startswith('NOTE') or content.startswith('WARNING'):
        return False
        
    # Keep type ignores, linters, encodings
    if content.startswith('type:') or content.startswith('pylint') or 'coding:' in content:
        return False

    words = content.split()
    if not words:
        return True # empty comment
    
    first_word = words[0]
    # If it's a typical AI verb or just a generic capitalized sentence
    if first_word in AI_VERBS:
        return True
        
    if content.startswith('---'):
        return True
        
    return False

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
        
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
        
    docstring_lines = set()
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False):
                # The first statement is the docstring
                doc_node = node.body[0]
                for i in range(doc_node.lineno, doc_node.end_lineno + 1):
                    docstring_lines.add(i)

    # Read original lines
    lines = source.splitlines()
    new_lines = []
    
    for i, line in enumerate(lines, 1):
        # 1. Skip function/class docstrings
        if i in docstring_lines:
            continue
            
        # 2. Check if it's an AI-like comment
        if is_ai_comment(line):
            continue
            
        new_lines.append(line)
        
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines) + '\n')

for root, dirs, files in os.walk('.'):
    if '.venv' in root or '.git' in root or 'data' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            clean_file(os.path.join(root, file))

print("Cleanup complete.")
