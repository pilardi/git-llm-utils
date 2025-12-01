from pydantic import BaseModel, Field
from typing import Any, Callable, Generator
from litellm import completion
import json
import sys

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
**Analyze the 'git diff --staged' output provided below and return only the generated commit message using text or markdown.**
"""

class LLMClient(BaseModel):
    """
    Interacts with the LLM using LiteLLM
    """
    use_emojis: bool = Field(description="If true, will instruct the model to generate feature emojis")
    model_name: str = Field(description="Base model to generate changeset descriptions")
    model_temperature: float = Field(description="How creative we want the response to be, 0 by default", default=0)
    api_key: str | None = Field(description="api key", default=None)
    api_url: str | None  = Field(description="base llm api", default=None)
    use_tools: bool = Field(description="If true, will provide the llm some contextual tooling", default=False)
    max_tokens: int = Field(description="How many tokens to send at most", default=262144)
    max_output_tokens: int = Field(description="How many tokens to get at most", default=65536)
    max_iterations: int = Field(description="How many tools interation to perform at most", default=5)
    respository_description: Callable[[],str] | None = Field(description="a human readable description of the repository", default=None)

    _deny_message = "Can't do that"

    @property
    def system_prompt(self) -> str:
        return self.use_emojis and f"{system_prompt_pre}\n{system_prompt_emojis}\n{system_prompt_pos}" or f"{system_prompt_pre}\n{system_prompt_pos}"

    def _responsitory_description(self) -> str:
        """
        Provides a description of the respository to the LLM if asked
        """
        if self.respository_description:
            try:
                return self.respository_description()
            except Exception as e:
                print(f"Failed to get repository description: {e}", file=sys.stderr)
        return ''

    def _available_tools(self) -> dict:
        return {
            "get_respository_description": self._responsitory_description,
        }
    
    def _tools(self) -> list[dict]:
        if self.use_tools:
            return [
                {
                    "type": "function",
                    "name": "get_respository_description",
                    "description": """
                        This function provides a description of the repository where the commit is happening, usualy this is the content of the README.md file.
                        It **ONLY** gives contextual information about the current respository and nothing else
                    """,
                    "function": self._responsitory_description
                }
            ]
        return []
    
    def message(self, diff_changes: str, stream : bool = False) -> Generator[str, Any, Any]:
        messages=[
            { 
                "role": "system", 
                "content": self.system_prompt 
            },
            {
                "role": "user",
                "content": diff_changes[:self.max_tokens]
            },
        ]
        tools = self._tools()
        available_tools = self._available_tools()
        incomplete = True
        interaction = 1
        while incomplete:
            response = completion(
                model=f'{self.model_name}',
                messages=messages,
                tools=interaction < self.max_iterations and tools or [],
                tool_choice="auto",
                base_url=self.api_url,
                api_key=self.api_key,
                max_tokens=self.max_output_tokens,
                stream=False,
                reasoning_effort='medium',
                temperature=self.model_temperature,
                verbosity="medium"
            )
            response_message = response.choices[0]["message"] # type: ignore
            tool_calls = response.choices[0]["message"]["tool_calls"] # type: ignore
            if tool_calls:
                messages.append(response_message)
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_tools.get(function_name, None)
                    function_args = json.loads(tool_call.function.arguments)
                    if function_to_call and interaction < self.max_iterations:
                        function_response = function_to_call(**function_args) or self._deny_message
                    else:
                        function_response = self._deny_message
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    })
            else:
                incomplete = False
                if stream:
                    for res in response.choices[0]["message"]["content"]: # type: ignore
                        yield res
                else:
                    yield response.choices[0]["message"]["content"] # type: ignore
