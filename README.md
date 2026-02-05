Backend:
  cd backend
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  uvicorn main:app --reload --host 0.0.0.0 --port 8000

Frontend:
  cd frontend
  npm install
  npm run dev

Or from project root:
  make dev
