.PHONY: all install install-backend install-frontend install-dev backend frontend dev test clean

all: install dev

install: install-backend install-frontend

install-backend:
	cd backend && python3 -m pip install -r requirements.txt -q

install-frontend:
	cd frontend && npm install --silent

install-dev:
	cd backend && python3 -m pip install -r requirements-dev.txt -q

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npx vite --host 0.0.0.0

dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@make -j 2 backend frontend

test:
	cd backend && python3 -m pytest tests -q

clean:
	rm -rf frontend/node_modules frontend/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/runs
