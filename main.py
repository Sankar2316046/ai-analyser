import os
import requests
from flask import Flask, Response, request, jsonify, make_response
import json
import html
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)

ALLOWED_ORIGIN = "https://cognify-teacher.vercel.app"

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response("", 200)
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    return response

CORS(
    app,
    origins=["https://cognify-teacher.vercel.app"],
    allow_headers=["Content-Type", "Authorization"],
    methods=["POST", "GET", "OPTIONS"]
)

@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return Response(status=200)


def call_ai(prompt, stream=False):
    REFERER_URL = os.getenv("REFERER_URL", "http://localhost:5000")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": REFERER_URL,
        "X-Title": "Exam Generator"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are an exam question generator. Respond ONLY with COMPLETE valid JSON objects, ONE QUESTION PER LINE. Never use arrays. Format EXACTLY: {\"question\":\"...\",\"options\":[\"A. text\",\"B. text\",\"C. text\",\"D. text\"],\"correct_answer\":\"A\",\"topic\":\"...\",\"difficulty\":\"...\"}. Escape all quotes properly. No extra text."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,  # Lower for consistency
        "stream": stream
    }
    
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=stream)
    
    if not stream:
        data = response.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return data
    
    # Streaming mode: yield content chunks
    buffer = ""
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                chunk_data = line[6:]
                if chunk_data == '[DONE]':
                    break
                try:
                    chunk = json.loads(chunk_data)
                    if 'choices' in chunk and chunk['choices'][0].get('delta', {}).get('content'):
                        content = chunk['choices'][0]['delta']['content']
                        buffer += content or ''
                        # Yield complete JSON lines
                        while '\n' in buffer:
                            nl_pos = buffer.find('\n')
                            json_line = buffer[:nl_pos]
                            buffer = buffer[nl_pos+1:]
                            if json_line.strip():
                                yield json_line.strip()
                except:
                    pass
    if buffer.strip():
        yield buffer.strip()


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json

    domain = data.get("domain")
    topics = data.get("topics", [])
    difficulty = data.get("difficulty")
    per_topic_count = int(data.get("question_count_per_topic", 2))

    total_expected = len(topics) * per_topic_count

    def generate_stream():
        yield json.dumps({
            "meta": {
                "domain": domain,
                "topics": topics,
                "per_topic": per_topic_count,
                "total_expected": total_expected
            }
        }) + "\n"

        for topic in topics:
            generated_for_topic = 0

            prompt = f"""
Generate EXACTLY {per_topic_count} {difficulty}-level MCQ questions ONLY for this topic.

Domain: {domain}
Topic: {topic}

RULES:
- Topic MUST be "{topic}"
- Output ONE JSON object per line
- No arrays, no markdown, no explanation

Format:
{{"question":"","options":["A. ","B. ","C. ","D. "],"correct_answer":"A","topic":"{topic}","difficulty":"{difficulty}"}}
"""

            for chunk in call_ai(prompt, stream=True):
                try:
                    question = json.loads(chunk)

                    # -------- HARD VALIDATION --------
                    if question.get("topic") != topic:
                        continue
                    if len(question.get("options", [])) != 4:
                        continue
                    # --------------------------------

                    # Normalize
                    letter_to_index = {"A": 0, "B": 1, "C": 2, "D": 3}
                    question["correct_answer"] = letter_to_index.get(
                        question["correct_answer"], 0
                    )
                    question["options"] = [html.unescape(opt[3:]) for opt in question["options"]]
                    question["question"] = html.unescape(question["question"])

                    yield json.dumps(question) + "\n"
                    generated_for_topic += 1

                    if generated_for_topic >= per_topic_count:
                        break

                except json.JSONDecodeError:
                    continue

        yield json.dumps({
            "done": True,
            "total": total_expected
        }) + "\n"

    return Response(generate_stream(), mimetype="application/x-ndjson")



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

if __name__ == "__main__":
    listen_port = int(os.getenv('X_ZOHO_CATALYST_LISTEN_PORT', 5000))  # Default to 5000 if not set
    app.run(host="0.0.0.0", port=listen_port)
