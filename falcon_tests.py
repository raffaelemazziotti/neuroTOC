import requests
import json
import tiktoken
import os

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
            "You are a strict neuroscience scientific article classifier.\n"
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


class ArticleClassifier2:
    def __init__(self, model='falcon3', host='http://localhost:11434'):
        self.model = model
        self.url = f'{host}/api/generate'
        self.known_keywords = set()
        self.enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def _format_prompt(self, articles):
        keyword_list = ', '.join(sorted(self.known_keywords)) if self.known_keywords else 'None'
        prompt_lines = [
            "You are a neuroscientist and must classify one or more scientific articles.",
            "Your task: decide if each article belongs to neuroscience, assign its type, and extract general and specific topic keywords.",
            "Purpose: to create a consistent keyword system for clustering articles by topic similarity.",
            "If the article is not related to neuroscience, write 'no' in item 1 and use only the single keyword 'other' in both keyword lists.",
            f"Known keywords: {keyword_list}. Assign one ore more keywords to each article.",
            "Output format must be *exactly* as specified. Do not add explanations, punctuation, labels, or text other than the required answers.",
            "Repeat the structure below for each article, replacing ## with the article number:",
            "",
            "Article ##:",
            "1. yes or no (answer only if the article is neuroscience-related)",
            "2. article type (choose only one: article, review, commentary, or other)",
            "3. general topic keywords (strictly pick the terms from known keywords)",
            "4. specific keywords (max 5, article specific keywords)",
            "",
            "Example of expected output:",
            "1. yes",
            "2. article",
            "3. anticipatory control, genetic models, neural synchronization",
            "4. LTP, development, fluoxetine",
            "",
            "Do not include any other text or explanations in your answer."
        ]
        for i, (title, abstract) in enumerate(articles, start=1):
            prompt_lines.append(f"Article {i}\nTitle: {title}\nAbstract: {abstract}\n")
        return '\n'.join(prompt_lines)

    def _parse_response(self, text):
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        parsed = {
            'neuroscience': None,
            'type': None,
            'generic_keywords': [],
            'specific_keywords': []
        }

        for line in lines:
            if line.startswith('1.'):
                parsed['neuroscience'] = line[2:].strip().lower()
            elif line.startswith('2.'):
                parsed['type'] = line[2:].strip().lower()
            elif line.startswith('3.'):
                parsed['generic_keywords'] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
            elif line.startswith('4.'):
                parsed['specific_keywords'] = [kw.strip() for kw in line[2:].split(',') if kw.strip()]
        # Update Keywords
        #if parsed['neuroscience'] and parsed['neuroscience'].strip().lower() =='yes':
            #self.known_keywords.update(parsed['generic_keywords'])
            #self.known_keywords.update(parsed['specific_keywords'])
        return parsed

    def classify(self, articles, parse=True, count_tokens=False):
        if isinstance(articles, tuple):
            articles = [articles]
        prompt = self._format_prompt(articles)
        if count_tokens:
            self.prompt_length(prompt)
        response = requests.post(self.url, json={
            'model': self.model,
            'prompt': prompt,
            'stream': False
        }).json()
        raw = response.get('response', '').strip()
        if not parse:
            return raw
        chunks = [chunk.strip() for chunk in raw.split('Article') if chunk.strip()]
        results = [self._parse_response(chunk) for chunk in chunks]
        return results[0] if len(results) == 1 else results

    def prompt_length(self, prompt):
        chars = len(prompt)
        tokens = len(self.enc.encode(prompt))
        print(f"Prompt length in chars: {chars}, tokens: {tokens}")
        return tokens, chars

    def save_keywords(self, path):
        """Save known keywords to a JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(sorted(self.known_keywords), f, ensure_ascii=False, indent=2)

    def load_keywords(self, path):
        """Load known keywords from a JSON file, safe if file missing or corrupted."""
        if not os.path.exists(path):
            self.known_keywords = set()
            print("Keyword file not found, starting with empty set.")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self.known_keywords = set(data)
            else:
                print("Invalid keyword file format, starting empty.")
                self.known_keywords = set()
        except Exception as e:
            print(f"Error loading keywords: {e}")
            self.known_keywords = set()

