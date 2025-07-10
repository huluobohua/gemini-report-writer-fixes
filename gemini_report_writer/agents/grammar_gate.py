
import requests
import json

class GrammarGateAgent:
    def __init__(self, languagetool_api_url="https://languagetool.org/api/v2/check"):
        self.api_url = languagetool_api_url

    def check_grammar_and_style(self, text):
        payload = {
            'language': 'en-US',
            'text': text
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        try:
            response = requests.post(self.api_url, data=payload, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            result = response.json()
            
            errors = []
            for match in result.get('matches', []):
                errors.append({
                    'message': match['message'],
                    'shortMessage': match.get('shortMessage', ''),
                    'context': match['context']['text'][match['context']['offset']:match['context']['offset'] + match['context']['length']],
                    'offset': match['context']['offset'],
                    'length': match['context']['length'],
                    'ruleId': match['rule']['id'],
                    'ruleDescription': match['rule']['description']
                })
            
            return {"status": "success", "errors": errors, "error_count": len(errors)}
        except requests.exceptions.RequestException as e:
            print(f"Error during LanguageTool API call: {e}")
            return {"status": "error", "message": str(e), "errors": [], "error_count": 0}

if __name__ == '__main__':
    grammar_checker = GrammarGateAgent()
    test_text = "This is a example of a text with some gramar errors. It also has a repeted word."
    result = grammar_checker.check_grammar_and_style(test_text)
    print(json.dumps(result, indent=2))

    test_text_clean = "This is an example of a text with no grammar errors."
    result_clean = grammar_checker.check_grammar_and_style(test_text_clean)
    print(json.dumps(result_clean, indent=2))
