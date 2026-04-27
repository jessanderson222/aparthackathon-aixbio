BioWatch Brief Setup Instructions

1. Backend Setup

- Create virtual environment:
python -m venv venv

- Activate:
Windows: venv\Scripts\activate
Mac/Linux: source venv/bin/activate

- Install dependencies:
python -m pip install fastapi uvicorn openai python-dotenv pydantic

- Create .env file:
OPENAI_API_KEY=your_api_key_here

- Ensure biowatch_corpus_fixed.json is in same directory as main.py

- Run backend:
python -m uvicorn main:app --reload

Backend runs at:
http://127.0.0.1:8000
Swagger UI:
http://127.0.0.1:8000/docs


2. Frontend Setup

- Navigate to frontend folder:
cd frontend

- Install dependencies:
npm install

- Start app:
npm start

Frontend runs at:
http://localhost:3000


3. Running the App

- Start backend first
- Start frontend
- Open browser at http://localhost:3000
- Submit report in UI


4. Troubleshooting

- If uvicorn fails:
python -m uvicorn main:app --reload

- If API key error:
Check .env file location and value

- If frontend can't connect:
Ensure backend is running on port 8000

- If no results:
Check corpus.json and scoring thresholds
