import re

with open('modules/notes.py', 'r') as f:
    content = f.read()

# We want to remove @group_only and @admin_required from notes commands, and insert our custom resolver.
# But actually, doing it via a decorator is cleaner!
