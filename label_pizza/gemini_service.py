"""
Gemini API service for generating video-based annotations.

This module provides integration with Google's Gemini API to automatically
generate questions, answers, and annotations based on video content.
"""

import json
from typing import Dict, List, Optional, Any
from google import genai
from google.genai import types


class GeminiService:
    """Service for Gemini API interactions for video analysis"""

    def __init__(self, api_key: str, model_name: str = 'gemini-2.5-flash'):
        """Initialize Gemini client

        Args:
            api_key: Gemini API key from user input
            model_name: Gemini model to use (e.g., 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash')
        """
        if not api_key:
            raise ValueError("Gemini API key is required")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate_questions_from_video(
        self,
        video_url: str,
        prompt: str,
        num_questions: int = 5,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Generate questions and answers based on video content

        Args:
            video_url: URL to the video (must be publicly accessible)
            prompt: Custom prompt to guide question generation
            num_questions: Number of questions to generate
            timeout: Request timeout in seconds

        Returns:
            dict: Generated questions with structure:
                {
                    "status": "success" | "error",
                    "questions": [
                        {
                            "question_text": str,
                            "question_type": "single" | "description",
                            "options": List[str],  # Only for single-choice
                            "correct_answer": str,
                            "explanation": str
                        },
                        ...
                    ],
                    "video_url": str,
                    "error": str  # Only if status == "error"
                }
        """
        import tempfile
        import urllib.request
        import time
        import os

        video_file = None
        uploaded_file = None

        try:
            # Build the complete prompt
            full_prompt = self._build_generation_prompt(prompt, num_questions)

            # Download and upload video to Gemini File API
            if video_url.startswith(('http://', 'https://')):
                # Download video to temporary file
                video_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')

                try:
                    urllib.request.urlretrieve(video_url, video_file.name)
                    video_file.close()

                    # Upload to Gemini File API
                    uploaded_file = self.client.files.upload(
                        file=video_file.name,
                        config=types.UploadFileConfig(display_name=f"video_{hash(video_url)}")
                    )

                    # Wait for file processing
                    while uploaded_file.state == "PROCESSING":
                        time.sleep(2)
                        uploaded_file = self.client.files.get(name=uploaded_file.name)

                    if uploaded_file.state == "FAILED":
                        raise ValueError(f"Video processing failed")

                    # Generate content with uploaded file
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[full_prompt, uploaded_file]
                    )

                except Exception as download_error:
                    raise ValueError(f"Failed to download or upload video: {str(download_error)}")
            else:
                raise ValueError(f"Invalid video URL: {video_url}")

            # Parse the response
            generated_text = response.text
            questions = self._parse_gemini_response(generated_text)

            return {
                "status": "success",
                "questions": questions,
                "video_url": video_url,
                "raw_response": generated_text
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "video_url": video_url
            }

        finally:
            # Clean up: delete temporary file
            if video_file and os.path.exists(video_file.name):
                try:
                    os.unlink(video_file.name)
                except:
                    pass

            # Clean up: delete uploaded file from Gemini
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except:
                    pass

    def answer_existing_questions(
        self,
        video_url: str,
        questions: List[Dict[str, Any]],
        custom_prompt: str = "",
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Answer existing questions based on video content

        Args:
            video_url: URL to the video
            questions: List of question dicts with 'text', 'type', and optionally 'options'
            custom_prompt: Optional additional context for answering
            timeout: Request timeout in seconds

        Returns:
            dict: Answers with structure:
                {
                    "status": "success" | "error",
                    "answers": {
                        "question_text": "answer_value",
                        ...
                    },
                    "video_url": str,
                    "error": str  # Only if status == "error"
                }
        """
        import tempfile
        import urllib.request
        import time
        import os

        video_file = None
        uploaded_file = None

        try:
            # Build prompt for answering existing questions
            full_prompt = self._build_answer_prompt(questions, custom_prompt)

            # Download and upload video to Gemini File API
            if video_url.startswith(('http://', 'https://')):
                # Download video to temporary file
                video_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')

                try:
                    urllib.request.urlretrieve(video_url, video_file.name)
                    video_file.close()

                    # Upload to Gemini File API
                    uploaded_file = self.client.files.upload(
                        file=video_file.name,
                        config=types.UploadFileConfig(display_name=f"video_{hash(video_url)}")
                    )

                    # Wait for file processing
                    while uploaded_file.state == "PROCESSING":
                        time.sleep(2)
                        uploaded_file = self.client.files.get(name=uploaded_file.name)

                    if uploaded_file.state == "FAILED":
                        raise ValueError(f"Video processing failed")

                    # Generate content with uploaded file
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[full_prompt, uploaded_file]
                    )

                except Exception as download_error:
                    raise ValueError(f"Failed to download or upload video: {str(download_error)}")
            else:
                raise ValueError(f"Invalid video URL: {video_url}")

            # Parse the response
            generated_text = response.text
            answers = self._parse_answer_response(generated_text, questions)

            return {
                "status": "success",
                "answers": answers,
                "video_url": video_url,
                "raw_response": generated_text
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "video_url": video_url,
                "answers": {}
            }

        finally:
            # Clean up: delete temporary file
            if video_file and os.path.exists(video_file.name):
                try:
                    os.unlink(video_file.name)
                except:
                    pass

            # Clean up: delete uploaded file from Gemini
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except:
                    pass

    def _build_answer_prompt(self, questions: List[Dict[str, Any]], custom_prompt: str) -> str:
        """Build prompt for answering existing questions

        Args:
            questions: List of question dictionaries
            custom_prompt: Additional context from user

        Returns:
            str: Complete formatted prompt
        """
        prompt = "Analyze this video and answer the following questions based on what you observe.\n\n"

        if custom_prompt:
            prompt += f"Additional context:\n{custom_prompt}\n\n"

        prompt += "Questions:\n\n"

        for i, q in enumerate(questions, 1):
            question_text = q.get('text', q.get('question_text', ''))
            question_type = q.get('type', q.get('question_type', 'single'))

            prompt += f"{i}. {question_text}\n"

            if question_type == 'single' and 'options' in q:
                options = q['options']
                prompt += f"   Options: {', '.join(options)}\n"
                prompt += f"   Type: Multiple choice (select one option)\n"
            else:
                prompt += f"   Type: Free text description\n"

            prompt += "\n"

        prompt += """
Please provide your answers in JSON format like this:
{
  "Question 1 text here": "Your answer",
  "Question 2 text here": "Your answer",
  ...
}

CRITICAL RULES:
- For multiple choice questions: Your answer MUST be EXACTLY one of the provided options
- Copy the option text EXACTLY as shown - do not paraphrase or modify
- Match the exact capitalization, punctuation, and spacing
- For description questions: Provide a clear and concise answer based on what you observe
- Use the exact question text as the key in your JSON response
- Respond ONLY with the JSON object, no additional text before or after
- Ensure all strings are properly escaped
- Use double quotes for JSON keys and values

Example for multiple choice:
If options are ["Walking", "Running", "Jumping"]
Your answer should be exactly "Running" (not "running" or "The person is running")
"""
        return prompt

    def _parse_answer_response(self, response_text: str, questions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Parse Gemini's answer response

        Args:
            response_text: Raw response from Gemini
            questions: Original questions for validation

        Returns:
            Dict mapping question text to answer value
        """
        # Remove markdown code blocks if present
        cleaned_text = response_text.strip()

        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]

        cleaned_text = cleaned_text.strip()

        try:
            # Parse JSON response
            answers = json.loads(cleaned_text)

            if not isinstance(answers, dict):
                raise ValueError("Response is not a JSON object")

            # Validate answers match questions
            validated_answers = {}
            for q in questions:
                question_text = q.get('text', q.get('question_text', ''))

                # Find answer for this question
                answer = answers.get(question_text)

                if answer is not None:
                    # For single-choice, validate against options
                    if q.get('type') == 'single' and 'options' in q:
                        if answer not in q['options']:
                            # Try multiple matching strategies
                            matched = False

                            # Strategy 1: Exact match (case-insensitive)
                            for option in q['options']:
                                if option.lower() == answer.lower():
                                    answer = option
                                    matched = True
                                    break

                            # Strategy 2: Substring match
                            if not matched:
                                for option in q['options']:
                                    if option.lower() in answer.lower() or answer.lower() in option.lower():
                                        answer = option
                                        matched = True
                                        break

                            # Strategy 3: Check if answer contains the option
                            if not matched:
                                for option in q['options']:
                                    # Remove common words and check
                                    option_words = set(option.lower().split())
                                    answer_words = set(answer.lower().split())
                                    if option_words.issubset(answer_words) or answer_words.issubset(option_words):
                                        answer = option
                                        matched = True
                                        break

                            # If still no match, use first option as fallback
                            if not matched and q['options']:
                                answer = q['options'][0]

                    validated_answers[question_text] = str(answer)

            return validated_answers

        except json.JSONDecodeError:
            # Fallback: return empty dict
            return {}

    def _build_generation_prompt(self, user_prompt: str, num_questions: int) -> str:
        """Build the complete prompt for Gemini

        Args:
            user_prompt: User-provided prompt for context
            num_questions: Number of questions to generate

        Returns:
            str: Complete formatted prompt
        """
        base_prompt = f"""Analyze this video and generate {num_questions} annotation questions based on the following context:

{user_prompt}

Generate questions that help annotators understand and label the video content. For each question, provide:

1. The question text
2. Question type (either "single" for multiple choice or "description" for free text)
3. For multiple choice questions: provide 3-5 answer options
4. The correct answer or expected response
5. A brief explanation of why this answer is correct

Format your response as a JSON array with this structure:
[
  {{
    "question_text": "What is the main action in this video?",
    "question_type": "single",
    "options": ["Walking", "Running", "Jumping", "Standing"],
    "correct_answer": "Running",
    "explanation": "The person is clearly running throughout the video"
  }},
  {{
    "question_text": "Describe the setting and environment",
    "question_type": "description",
    "correct_answer": "Urban park with trees and pathways during daytime",
    "explanation": "The video shows a city park environment with visible greenery"
  }}
]

IMPORTANT:
- Respond ONLY with valid JSON array
- No additional text before or after the JSON
- Ensure all strings are properly escaped
- Use double quotes for JSON keys and values
"""
        return base_prompt

    def _parse_gemini_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse Gemini's response to extract structured questions

        Args:
            response_text: Raw text response from Gemini

        Returns:
            List of question dictionaries
        """
        # Try to find JSON in the response
        # Remove markdown code blocks if present
        cleaned_text = response_text.strip()

        # Remove markdown JSON code blocks
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]

        cleaned_text = cleaned_text.strip()

        try:
            # Try to parse as JSON
            questions = json.loads(cleaned_text)

            # Validate structure
            if not isinstance(questions, list):
                raise ValueError("Response is not a JSON array")

            # Validate each question has required fields
            validated_questions = []
            for q in questions:
                if "question_text" not in q or "question_type" not in q:
                    continue

                # Ensure question_type is valid
                if q["question_type"] not in ["single", "description"]:
                    q["question_type"] = "single"

                # For single-choice, ensure options exist
                if q["question_type"] == "single" and "options" not in q:
                    q["options"] = ["Yes", "No", "Unclear"]

                # Ensure correct_answer exists
                if "correct_answer" not in q:
                    if q["question_type"] == "single" and "options" in q:
                        q["correct_answer"] = q["options"][0]
                    else:
                        q["correct_answer"] = ""

                validated_questions.append(q)

            return validated_questions

        except json.JSONDecodeError as e:
            # Fallback: try to extract questions using regex
            return self._fallback_parse(response_text)

    def _fallback_parse(self, text: str) -> List[Dict[str, Any]]:
        """Fallback parser if JSON parsing fails

        Args:
            text: Raw response text

        Returns:
            List of question dictionaries (may be empty if parsing fails)
        """
        # Simple fallback: return empty list or basic structure
        # In production, you might want more sophisticated parsing
        return []


def test_gemini_connection(api_key: str) -> Dict[str, Any]:
    """Test Gemini API connection

    Args:
        api_key: Gemini API key

    Returns:
        dict with status and message
    """
    try:
        client = genai.Client(api_key=api_key)

        # Simple test prompt
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents="Say 'API connection successful' if you can read this."
        )

        return {
            "status": "success",
            "message": "API connection successful",
            "response": response.text[:100]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
