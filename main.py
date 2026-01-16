import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)

# Enable CORS for Next.js frontend
CORS(app, origins=["http://localhost:3000"])

# -----------------------------
# Call OpenRouter
# -----------------------------
def call_ai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Exam Generator"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are an exam question generator. Respond ONLY in valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
    data = response.json()

    # Proper error handling
    if "choices" not in data:
        return data

    return data["choices"][0]["message"]["content"]


# -----------------------------
# API Endpoint
# -----------------------------
@app.route("/generate", methods=["POST"])
def generate():
    data = request.json

    domain = data.get("domain")
    topics = data.get("topics", [])
    difficulty = data.get("difficulty")
    count = data.get("question_count_per_topic", 5)

    prompt = f"""
Generate {count} {difficulty}-level MCQ questions for each topic below.

Domain: {domain}
Topics: {topics}

Return STRICT JSON in this format:

{{
  "questions": [
    {{
      "question": "",
      "options": ["", "", "", ""],
      "correct_answer": "",
      "topic": "",
      "difficulty": ""
    }}
  ]
}}
"""

    ai_output = call_ai(prompt)

    return jsonify({
        "input": data,
        "output": ai_output
    })


if __name__ == "__main__":
    app.run(debug=True)
