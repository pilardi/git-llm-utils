from ollama import chat
from pydantic import BaseModel, Field
from typing import Any, Generator

system_prompt_pre = """
You are an expert software engineer and technical writer. Your sole task is to analyze the provided **'git diff --staged' output** and generate a professional, descriptive, and concise **Git commit message**.

Your response **MUST ONLY** contain the commit message. **DO NOT** include any conversational text, explanations, or dialogue (e.g., "Here is the commit message:", "Based on the changes...").

The generated message should adhere to the following structure and best practices:

1.  **Subject Line (Max 50 characters):** A single line summarizing the change. Use the imperative mood (e.g., "Fix", "Add", "Refactor") and categorize the change (e.g., `feat:`, `fix:`, `refactor:`, `docs:`, `style:`).
2.  **Body (Optional, separated by a blank line):** Detailed, bulleted description of *what* the changes are and *why* they were made. Focus on the user-facing or technical implications, not the mechanical details of the diff.

**Example Structure:**

```

feat: Implement user profile validation

  - Add server-side validation for email format.
  - Update API response to return detailed error codes for invalid input.
  - Remove deprecated 'is_active' flag from the User model.

```

"""

### ref: https://gitmoji.dev/ 
system_prompt_emojis = """
Use the following emojis within the subject line or the body (if applicable):

🎨
Improve structure / format of the code.

⚡️
Improve performance.

🔥
Remove code or files.

🐛
Fix a bug.

🚑️
Critical hotfix.

✨
Introduce new features.

📝
Add or update documentation.

🚀
Deploy stuff.

💄
Add or update the UI and style files.

🎉
Begin a project.

✅
Add, update, or pass tests.

🔒️
Fix security or privacy issues.

🔐
Add or update secrets.

🔖
Release / Version tags.

🚨
Fix compiler / linter warnings.

🚧
Work in progress.

💚
Fix CI Build.

⬇️
Downgrade dependencies.

⬆️
Upgrade dependencies.

📌
Pin dependencies to specific versions.

👷
Add or update CI build system.

📈
Add or update analytics or track code.

♻️
Refactor code.

➕
Add a dependency.

➖
Remove a dependency.

🔧
Add or update configuration files.

🔨
Add or update development scripts.

🌐
Internationalization and localization.

✏️
Fix typos.

💩
Write bad code that needs to be improved.

⏪️
Revert changes.

🔀
Merge branches.

📦️
Add or update compiled files or packages.

👽️
Update code due to external API changes.

🚚
Move or rename resources (e.g.: files, paths, routes).

📄
Add or update license.

💥
Introduce breaking changes.

🍱
Add or update assets.

♿️
Improve accessibility.

💡
Add or update comments in source code.

🍻
Write code drunkenly.

💬
Add or update text and literals.

🗃️
Perform database related changes.

🔊
Add or update logs.

🔇
Remove logs.

👥
Add or update contributor(s).

🚸
Improve user experience / usability.

🏗️
Make architectural changes.

📱
Work on responsive design.

🤡
Mock things.

🥚
Add or update an easter egg.

🙈
Add or update a .gitignore file or grotesque solution.

📸
Add or update snapshots.

⚗️
Perform experiments.

🔍️
Improve SEO.

🏷️
Add or update types.

🌱
Add or update seed files.

🚩
Add, update, or remove feature flags.

🥅
Catch errors.

💫
Add or update animations and transitions.

🗑️
Deprecate code that needs to be cleaned up.

🛂
Work on code related to authorization, roles and permissions.

🩹
Simple fix for a non-critical issue.

🧐
Data exploration/inspection.

⚰️
Remove dead code.

🧪
Add a failing test.

👔
Add or update business logic.

🩺
Add or update healthcheck.

🧱
Infrastructure related changes.

🧑‍💻
Improve developer experience.

💸
Add sponsorships or money related infrastructure.

🧵
Add or update code related to multithreading or concurrency.

🦺
Add or update code related to validation.

✈️
Improve offline support.

🚢🇮🇹
:shipit:
All done, shipt it!
"""

system_prompt_pos = """
**Analyze the 'git diff --staged' output provided below and return only the generated commit message.**
"""

class LLMClient(BaseModel):

    use_emojis: bool = Field(default=False, description="If true, will instruct the model to generate feature emojis")
    model_name: str = Field(default="qwen3-coder:480b-cloud", description="Base model to generate changeset descriptions")
    model_temperature: float = Field(default=0, description="How creative we want the response to be, 0 by default")

    @property
    def system_prompt(self):
        return self.use_emojis and f"{system_prompt_pre}\n{system_prompt_emojis}\n{system_prompt_pos}" or f"{system_prompt_pre}\n{system_prompt_pos}"

    def message(self, diff_changes: str, stream : bool = False) -> Generator[str, Any, Any]:
        """
        Generates a commit message from the LLM
        Args:
            diff_changes (str): Git diff content.
            stream: if True will push the messages as they arrive from the llm
        Returns:
            str: the commit message.
        """
        response = chat(
            model=self.model_name,
            messages=[
                { 
                    "role": "system", 
                    "content": self.system_prompt 
                },
                {
                    "role": "user",
                    "content": diff_changes
                },
            ],
            options={
                'temperature': self.model_temperature
            },
            stream=stream
        )
        if stream:
            for res in response:
                yield str(res["message"]["content"]) # type: ignore
        else:
            yield response["message"]["content"] # type: ignore
