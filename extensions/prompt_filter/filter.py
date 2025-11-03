import requests
import os
from typing import Dict
import time
from openai import OpenAI
import ollama
from better_profanity import profanity
from dotenv import load_dotenv


class ContentFilter:
    def __init__(self):
        load_dotenv()
        self.OLLAMA_HOST = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
        self.BAD_WORDS_URL = "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/it"
        self.CACHE_FILE = "bad_words_it_cache.txt"

    def load_it_bad_words(self):
        # Check if cache exists
        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                return [word.strip().lower() for word in f if word.strip()]
        
        # Download if not cached
        response = requests.get(self.BAD_WORDS_URL, timeout=5)
        response.raise_for_status()
        
        # Save to cache
        with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        return [word.strip().lower() for word in response.text.splitlines() if word.strip()]


    def layer1_regex(self, text: str) -> Dict:
        profanity.load_censor_words()
        self.italian_bad_words = self.load_it_bad_words()
        profanity.add_censor_words(self.italian_bad_words)
        is_bad = profanity.contains_profanity(text)
        
        return {"is_inappropriate": is_bad, "reason": "profanity"}
    
    def layer2_openai(self, text: str) -> dict:
        client = OpenAI()
        response = client.moderations.create(
            model="omni-moderation-latest",
            input=text,
        )
        return response

    def layer3_llama(self, text: str) -> Dict:
        """AI-powered content analysis"""
        prompt = f"""You are a content safety classifier for a text-to-image platform. Analyze if this prompt is safe.
                Prompt to analyze: "{text}"
                Classify as:
                - SAFE: Appropriate content (landscapes, objects, people in normal situations, art, etc.)
                - UNSAFE: Sexual content, violence, hate speech, drugs, weapons, or anything harmful
                Consider context: Medical/educational content about anatomy can be SAFE. Historical content can be SAFE.
                Be strict on: Anything sexual, violent, hateful, or involving minors.
                Respond with ONLY one word: SAFE or UNSAFE
                Answer:"""
        
        try:
            start_time = time.time()
            data = {
                "model": self.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
            
            client = ollama.Client(host=self.OLLAMA_HOST)
            response = client.generate(
                model=self.OLLAMA_MODEL,
                prompt=prompt
            )
        
            if response.done == True:
                result = response.response
                processing_time = time.time() - start_time
                
                # Check for SAFE in response
                if "SAFE" in result and "UNSAFE" not in result:
                    return {
                        "safe": True,
                        "blocked": False,
                        "reason": "Approved by AI",
                        "layer": "llama",
                        "confidence": 90,
                        "processing_time": f"{processing_time:.2f}s"
                    }
                else:
                    # Block if UNSAFE or uncertain
                    return {
                        "safe": False,
                        "blocked": True,
                        "reason": "Flagged by AI as potentially inappropriate",
                        "layer": "llama",
                        "confidence": 85,
                        "processing_time": f"{processing_time:.2f}s"
                    }
            else:
                # If Llama fails, be cautious and block
                return {
                    "safe": False,
                    "blocked": True,
                    "reason": "Safety check failed, blocked as precaution",
                    "layer": "3-llama-not-sure",
                    "confidence": 50
                }
                
        except Exception as e:
            print(f"Llama error: {e}")
            # On error, block to be safe
            return {
                "safe": False,
                "blocked": True,
                "reason": "request to llama could not be established, blocked as precaution",
                "layer": "3-llama-error",
                "confidence": 50,
                "error": str(e)
            }
    

    def check_prompt(self, text: str) -> Dict:
        
        # 1st layer check (very obvious cases)
        first_layer_check = self.layer1_regex(text)
        if (first_layer_check["is_inappropriate"]):
            return {"is_inappropriate": True, "layer": "1", "reason": first_layer_check["reason"]}

        # 2nd layer check (using ML)
        try:
            second_layer_check = self.layer2_openai(text)
            if (second_layer_check.results[0].flagged):
                which_flag = ""
                for key, value in second_layer_check.results[0]["categories"]:
                    if value:
                        which_flag = key
                        break
                
                return {"is_inappropriate": True, "layer": "2", "reason": which_flag}
        except Exception as e:
            pass
    
        third_layer_check = self.layer3_llama(text)
        if (third_layer_check["blocked"] == True):
            return {"is_inappropriate": True, "layer": "3", "reason": third_layer_check["reason"]}


        return {"is_inappropriate": False, "layer": None, "reason": None}