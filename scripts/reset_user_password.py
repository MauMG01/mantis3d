#!/usr/bin/env python3
"""Reset one-off de contraseña (soporte) sin Shell de Render.

1. En Render → mantis-db → Connect → copia External Database URL
2. En Terminal:

  cd ~/Desktop/conversor3D
  export DATABASE_URL='pega-aqui-la-url-external'
  .venv/bin/python scripts/reset_user_password.py usmauriciomg@gmail.com 'MantisTemp2026!'
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if len(sys.argv) != 3:
    print(
        "Uso: python scripts/reset_user_password.py EMAIL NUEVA_CONTRASEÑA",
        file=sys.stderr,
    )
    raise SystemExit(2)

if not os.environ.get("DATABASE_URL"):
    print(
        "Define DATABASE_URL con la External Database URL de Render (mantis-db → Connect).",
        file=sys.stderr,
    )
    raise SystemExit(2)

# Evitar que backend/.env (sqlite local) pise la URL de Render.
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].strip()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Importar DESPUÉS de fijar DATABASE_URL
from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def main() -> int:
    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print("USER_NOT_FOUND")
            return 1
        user.hashed_password = hash_password(password)
        db.add(user)
        db.commit()
        print(
            "OK",
            user.email,
            "plan=",
            user.plan,
            "stripe=",
            bool(user.stripe_customer_id),
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
