.PHONY: backend frontend dev

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm install && npm run dev

dev:
	make -j 2 backend frontend
