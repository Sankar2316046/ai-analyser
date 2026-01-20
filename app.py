from flask import Flask, request, jsonify

app = Flask(__name__)

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
    app.run(debug=True)
