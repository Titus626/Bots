import psycopg2
import openai
import os
import json

openai.api_key = os.environ["OPENAI_API_KEY"]

class DatabaseManager:
    def __init__(self, database_name, database_user, database_password):
        self.conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database=database_name,
            user=database_user,
            password=database_password
        )
        self.cur = self.conn.cursor()

    def get_user_profile(self, user_id):
        self.cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
        profile = self.cur.fetchone()

        if profile:
            profile_data = json.loads(profile[1])
            return profile_data
        else:
            return {}

class OpenAIHelper:
    def __init__(self, engine="davinci"):
        self.engine = engine

    def generate_response(self, prompt):
        response = openai.Completion.create(
            engine=self.engine,
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )
        return response["choices"][0]["text"].strip()

class Chatbot:
    def __init__(self, db_manager, openai_helper):
        self.db_manager = db_manager
        self.openai_helper = openai_helper

    def generate_response(self, message_dict):
        user_profile = self.db_manager.get_user_profile(message_dict["user"])
        prompt = self._generate_prompt(user_profile)
        response = self.openai_helper.generate_response(prompt)
        return response

    def _generate_prompt(self, user_profile):
        prompt = ""

        if user_profile.get("avg_sentiment", 0) > 0:
            prompt += "The user seems happy."
        elif user_profile.get("avg_sentiment", 0) < 0:
            prompt += " The user seems upset."
        else:
            prompt += "The user has a neutral emotion."

        if user_profile.get("most_common_topic", ""):
            prompt += f" They are interested in {user_profile['most_common_topic']}."

        if user_profile.get("avg_interaction_time", ""):
            prompt += f" They typically interact with the bot during the {user_profile['avg_interaction_time']}."

        if user_profile.get("avg_message_length", ""):
            prompt += f" Their messages are usually {user_profile['avg_message_length']} in length."

        prompt += " How should I respond?"

        return prompt

if __name__ == "__main__":
    db_manager = DatabaseManager("your-db-name", "your-db-username", "your-db-password")
    openai_helper = OpenAIHelper()
    chatbot = Chatbot(db_manager, openai_helper)

    while True:
        message = input("Enter message: ")
        message_dict = {"user": "user-id", "message": message}
        response = chatbot.generate_response(message_dict)
        print(f"Response: {response}")
