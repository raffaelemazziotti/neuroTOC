import requests
import json
import tiktoken

class FalconChat:
    def __init__(self, model='falcon3', directive=None):
        self.model = model
        self.history = []
        self.directive = directive

    def set_directive(self, directive):
        """Set or update the system directive."""
        self.directive = directive

    def clear_history(self):
        """Clear the chat history."""
        self.history = []

    def ask(self, prompt, history=True):
        """Ask the model a question with optional history tracking."""
        # Construct prompt with history
        full_prompt = ""

        if self.directive:
            full_prompt += f"[System directive]: {self.directive}\n"

        for turn in self.history:
            if turn['role'] == 'user':
                full_prompt += f"User: {turn['content']}\n"
            else:
                full_prompt += f"Assistant: {turn['content']}\n"

        full_prompt += f"User: {prompt}\nAssistant: "

        # Send request
        response = requests.post('http://localhost:11434/api/generate', json={
            'model': self.model,
            'prompt': full_prompt,
            'stream': False
        })

        data = response.json()
        answer = data.get('response', '')

        if history:
            self.history.append({'role': 'user', 'content': prompt})
            self.history.append({'role': 'assistant', 'content': answer})

        return answer

class ArticleClassifier:
    def __init__(self, model='falcon3', base_url='http://localhost:11434'):
        self.model = model
        self.base_url = base_url
        self.history = []
        self.keywords_memory = set()

        self.system_directive = (
            "You are a strict scientific article classifier.\n"
            "Given a title and optional abstract, always answer with this exact format:\n"
            "1. neuroscience or not\n"
            "2. one of these options: article, review, commentary, or other\n"
            "3. generic keywords (max 5, comma-separated, NO generic words like 'neuroscience', but descriptive of the field and the subject)\n"
            "4. specific keywords (max 5, comma-separated, very precise to the article)\n"
            "No other text or commentary — just the 4 numbered lines."
        )

    def classify_article(self, title, abstract, remember=True, return_parsed=True):
        article_input = f"Title: {title}\nAbstract: {abstract}"
        prompt = self.system_directive + "\n\n" + article_input

        if self.history:
            full_prompt = self._build_history() + "\n\n" + prompt
        else:
            full_prompt = prompt

        response = self._query_model(full_prompt)

        if remember:
            self.history.append({"title": title, "abstract": abstract, "response": response})

        if return_parsed:
            return self._parse_response(response)
        else:
            return response

    def _query_model(self, prompt):
        url = f"{self.base_url}/api/generate"
        response = requests.post(url, json={
            'model': self.model,
            'prompt': prompt,
            'stream': False
        })
        data = response.json()
        return data.get("response", "No response")

    def _build_history(self):
        history_prompts = ""
        for item in self.history:
            title = item["title"]
            abstract = item["abstract"]
            history_prompts += f"Previous Article:\nTitle: {title}\nAbstract: {abstract}\n\n"
        return history_prompts

    def _parse_response(self, response):
        lines = response.strip().split('\n')
        result = {}
        try:
            for line in lines:
                if line.startswith("1."):
                    result["is_neuroscience"] = line[2:].strip().lower()
                elif line.startswith("2."):
                    result["article_type"] = line[2:].strip().lower()
                elif line.startswith("3."):
                    result["generic_keywords"] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
                elif line.startswith("4."):
                    result["specific_keywords"] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
        except Exception as e:
            print("Failed to parse response:", response)
            raise e
        return result

    def get_keywords(self, return_as_dict=True):
        if return_as_dict:
            return {kw: True for kw in sorted(self.keywords_memory)}
        else:
            return sorted(self.keywords_memory)

import requests

class ArticleClassifier2:
    def __init__(self, model='falcon3', host='http://localhost:11434'):
        self.model = model
        self.url = f'{host}/api/generate'
        self.known_keywords = set()
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def _format_prompt(self, title, abstract):
        keyword_list = ', '.join(sorted(self.known_keywords)) if self.known_keywords else 'None'
        return (
            "You are an expert Neuroscientist. You will be given a scientific article. Classify it and extract keywords.\n"
            f"You already know these keywords: {keyword_list}.\n"
            "If any of them apply, reuse them. If new keywords are needed, create them. Be consistent with naming.\n"
            "Return the result in this format  (just the answers not other descriptions):\n"
            "1. is it neuroscience? you must say yes or no, nothing else (e.g.: yes)\n"
            "2. article type (e.g., article, review, commentary, other. If other don't add comments)\n"
            "3. generic keywords (max 5, generic description, avoid neuroscience as keyword)\n"
            "4. specific keywords (max 5, avoid too specific words)\n\n"
            f"Title: {title}\n"
            f"Abstract: {abstract}"
        )

    def _parse_response(self, text):
        lines = text.strip().split('\n')
        parsed = {
            'neuroscience': None,
            'type': None,
            'generic_keywords': [],
            'specific_keywords': []
        }
        for line in lines:
            if line.startswith('1.'):
                parsed['neuroscience'] = line[2:].strip()
            elif line.startswith('2.'):
                parsed['type'] = line[2:].strip()
            elif line.startswith('3.'):
                parsed['generic_keywords'] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
            elif line.startswith('4.'):
                parsed['specific_keywords'] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
        self.known_keywords.update(parsed['generic_keywords'])
        self.known_keywords.update(parsed['specific_keywords'])
        return parsed

    def classify(self, title, abstract='', parse=True):
        prompt = self._format_prompt(title, abstract)
        self.prompt_length(prompt)
        response = requests.post(self.url, json={
            'model': self.model,
            'prompt': prompt,
            'stream': False
        })
        response = response.json()
        #print('raw',response)
        output = response.get('response', '').strip()
        return self._parse_response(output) if parse else output

    def classify_batch(self, articles, parse=True):
        keyword_list = ', '.join(sorted(self.known_keywords)) if self.known_keywords else 'None'
        prompt_lines = [
            "You are an expert Neuroscientist. You will be given multiple scientific articles. Classify them and extract keywords.",
            f"You already know these keywords: {keyword_list}.\n"
            "If any of them apply, reuse them. If new keywords are needed, create them. Be consistent with naming.\n",
            "For each article, return the result in this format (just the answers not other descriptions):\n",
            "Article ##:\n",
            "1. is it neuroscience? you must say yes or no, nothing else (e.g.: yes)\n",
            "2. article type (e.g., article, review, commentary, other. If other don't add comments)\n",
            "3. generic keywords (max 5, generic description, avoid neuroscience as keyword)\n"
            "4. specific keywords (max 5, avoid too specific words)\n"
        ]
        for i, (title, abstract) in enumerate(articles, start=1):
            prompt_lines.append(f"Article {i}\nTitle: {title}\nAbstract: {abstract}\n")
        prompt = '\n'.join(prompt_lines)
        self.prompt_length(prompt)
        response = requests.post(self.url, json={
            'model': self.model,
            'prompt': prompt,
            'stream': False
        })
        response = response.json()
        raw = response.get('response', '').strip()
        if not parse:
            return raw

        # Split by article result assuming "Article N" headers
        chunks = [chunk.strip() for chunk in raw.split('Article') if chunk.strip()]
        results = []
        for chunk in chunks:
            parsed = self._parse_response(chunk)
            results.append(parsed)
        return results

    def prompt_length(self,prompt):
        chars = len(prompt)
        tokens = len(self.enc.encode(prompt))
        print(f"Prompt length in chars: {chars} and tokens: {tokens}")
        return tokens, chars
