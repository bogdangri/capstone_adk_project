

def clean_model_json(raw: str) -> str:
    """
    Take the raw model output and return a clean JSON string:
   
    """
    text = raw.strip()

    # Handle code fences:
    # Case 1: multi-line fenced block
    if text.startswith("```"):
        lines = text.splitlines()

        # Drop first line if it's ``` or ```json
        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        # Drop last line if it's ``` 
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # Case 2: inline ```json ... ``` on one line (less common)
    if text.startswith("```json") and text.endswith("```"):
        text = text[len("```json"): -3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()

    # Fix invalid \' escapes (not valid in JSON, we want plain single quote)
    text = text.replace("\\'", "'")

    return text



