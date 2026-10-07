import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

AI_OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "num_predict": 256,
}


def ask_codetrack_ai(prompt):

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": AI_OPTIONS
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return {
            "success": True,
            "response": data.get("response", "")
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "CodeTrack AI took too long to respond."
        }

    except requests.exceptions.RequestException as e:
        print("Ollama API error:", e)

        return {
            "success": False,
            "error": "CodeTrack AI could not connect to Ollama."
        }

    except Exception as e:
        print("CodeTrack AI error:", e)

        return {
            "success": False,
            "error": str(e)
        }