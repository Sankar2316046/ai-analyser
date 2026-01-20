import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
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
# Skill Analysis Endpoint
# -----------------------------
@app.route("/skill-analysis", methods=["POST"])
def skill_analysis():
    data = request.json

    total_questions = data.get("total_questions", 0)
    topic_scores = data.get("topic_scores", {})

    # -----------------------------
    # Overall score & level
    # -----------------------------
    total_correct = sum(t.get("correct", 0) for t in topic_scores.values())
    overall_percentage = (total_correct / total_questions) * 100 if total_questions else 0

    if overall_percentage >= 70:
        overall_level = "Advanced"
    elif overall_percentage >= 40:
        overall_level = "Intermediate"
    else:
        overall_level = "Beginner"

    strengths = []
    weaknesses = []
    recommendations = []
    next_topics = []

    # -----------------------------
    # Topic-wise evaluation
    # -----------------------------
    for topic, stats in topic_scores.items():
        percentage = stats.get("percentage", 0)

        # 🔴 VERY WEAK
        if percentage == 0:
            weaknesses.append({
                "topic": topic,
                "reason": "Very weak in basics"
            })

            recommendations.append({
                "topic": topic,
                "suggestion": f"Read {topic} again from basics like core concepts, syntax and examples"
            })

            next_topics.append(f"Read {topic} again")

        # 🟡 WEAK / AVERAGE
        elif percentage < 70:
            weaknesses.append({
                "topic": topic,
                "reason": "Basic understanding but lacks consistency"
            })

            strengths.append({
                "topic": topic,
                "reason": "Some concepts are clear but need more practice"
            })

            recommendations.append({
                "topic": topic,
                "suggestion": f"Practice more {topic} problems and revise weak areas"
            })

            next_topics.append(f"Improve {topic} practice")

        # 🟢 STRONG
        else:
            strengths.append({
                "topic": topic,
                "reason": "Strong understanding of concepts"
            })

            recommendations.append({
                "topic": topic,
                "suggestion": f"Continue strengthening {topic} with real-world examples"
            })

            next_topics.append(f"Advance in {topic}")

    # -----------------------------
    # Final response (STRICT JSON)
    # -----------------------------
    result = {
        "overall_level": overall_level,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "next_topics": next_topics
    }

    return jsonify(result)


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

    output_str = json.dumps(ai_output) if isinstance(ai_output, dict) else ai_output

    return jsonify({
        "input": data,
        "output": output_str
    })


if __name__ == "__main__":
    app.run(debug=True)
