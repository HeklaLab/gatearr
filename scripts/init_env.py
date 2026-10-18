"""Create .env with independent cryptographically random secrets. Standard library only."""
from pathlib import Path
import secrets
import os

root = Path(__file__).resolve().parents[1]
content = (root / '.env.example').read_text()
content = content.replace('SECRET_KEY=\n', 'SECRET_KEY='+secrets.token_urlsafe(48)+'\n')
try:
    descriptor = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit('.env existe déjà ; aucune modification effectuée.')
with os.fdopen(descriptor, 'w') as output:
    output.write(content)
print('.env créé. Les connexions se configurent dans l’assistant au premier lancement.')
