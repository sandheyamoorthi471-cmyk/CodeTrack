import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"
AI_OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "num_predict": 256,
}


def ask_codetrack_ai(prompt):
    """
    Send a prompt to the local CodeTrack AI model.
    """

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
                "options": AI_OPTIONS,
            },
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        return {
            "success": True,
            "response": data.get(
                "response",
                "I couldn't generate a response."
            ),
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": (
                "CodeTrack AI is not running. "
                "Please make sure Ollama is running."
            ),
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": (
                "CodeTrack AI took too long to respond."
            ),
        }

    except Exception as e:
        print("CodeTrack AI error:", e)

        return {
            "success": False,
            "error": str(e),
        }