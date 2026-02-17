.PHONY: all install install-backend install-frontend backend frontend dev clean

all: install dev

install: install-backend install-frontend

install-backend:
	cd backend && pip install -r requirements.txt -q

install-frontend:
	cd frontend && npm install --silent

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npx vite --host 0.0.0.0

dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@make -j 2 backend frontend

clean:
	rm -rf frontend/node_modules frontend/dist backend/__pycache__ backend/dominoes/__pycache__
