from typing import Dict, Optional, List
import json
import logging
from litellm import acompletion
from ..core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for analyzing changelogs using LLMs"""

    ANALYSIS_PROMPT = """You are an expert at analyzing software changelogs and identifying breaking changes.

I need you to analyze the following changelog for a Docker container update and provide a comprehensive assessment.

Image: {image_name}
Update: {from_version} → {to_version}

Changelog:
{changelog}

Please analyze this changelog and provide a detailed JSON response with the following structure:

{{
    "executive_summary": "Brief 2-3 sentence summary of the update",
    "risk_level": "low|medium|high|critical",
    "safe_to_auto_update": true/false,
    "has_breaking_changes": true/false,
    "breaking_changes": [
        {{
            "title": "Brief title",
            "description": "Detailed description",
            "category": "api|config|behavior|dependency|other",
            "severity": "low|medium|high|critical",
            "affected_components": ["list", "of", "affected", "components"],
            "workaround": "How to handle this change",
            "migration_steps": ["step 1", "step 2"]
        }}
    ],
    "config_changes_required": [
        {{
            "type": "environment_variable|volume|port|other",
            "description": "What needs to be changed",
            "action": "What the user needs to do"
        }}
    ],
    "database_migrations_required": true/false,
    "migration_notes": "Details about required migrations",
    "deprecated_features": ["list of deprecated features"],
    "removed_features": ["list of removed features"],
    "new_features": ["list of new features"],
    "improvements": ["list of improvements"],
    "bug_fixes": ["list of bug fixes"],
    "security_fixes": [
        {{
            "description": "Security issue description",
            "cve_id": "CVE-XXXX-XXXXX or null",
            "severity": "low|medium|high|critical"
        }}
    ],
    "dependency_updates": [
        {{
            "name": "dependency name",
            "from_version": "old version",
            "to_version": "new version",
            "breaking": true/false
        }}
    ],
    "minimum_version_requirements": {{
        "component": "minimum version"
    }},
    "action_items": [
        {{
            "action": "What needs to be done",
            "priority": "low|medium|high|critical",
            "when": "before_update|after_update|monitoring"
        }}
    ],
    "testing_recommendations": ["list of things to test after update"],
    "estimated_update_time_minutes": 5,
    "rollback_complexity": "easy|moderate|difficult",
    "recommended_action": "Specific recommendation for this update",
    "risk_factors": ["factor 1", "factor 2"],
    "requires_downtime": true/false,
    "estimated_downtime_minutes": 5,
    "requires_human_review": true/false,
    "human_review_reason": "Why human review is needed"
}}

Important:
1. Be thorough in identifying breaking changes - these are critical
2. Consider configuration changes, API changes, behavior changes, and dependency updates
3. Assess whether this update is safe to apply automatically
4. If information is unclear or missing, indicate that human review is recommended
5. Be specific in action items and migration steps
6. Consider the impact on existing functionality

Provide ONLY the JSON response, no additional text.
"""

    def __init__(self):
        self.model_primary = settings.LLM_MODEL_PRIMARY
        self.model_fallback = settings.LLM_MODEL_FALLBACK
        self.model_local = settings.LLM_MODEL_LOCAL
        self.use_local_for_sensitive = settings.USE_LOCAL_FOR_SENSITIVE

    async def analyze_changelog(self, image_name: str, from_version: str,
                                to_version: str, changelog: str,
                                is_sensitive: bool = False) -> Optional[Dict]:
        """
        Analyze a changelog using LLM
        Returns structured analysis or None if failed
        """
        try:
            # Determine which model to use
            model = self._select_model(is_sensitive)

            # Prepare prompt
            prompt = self.ANALYSIS_PROMPT.format(
                image_name=image_name,
                from_version=from_version,
                to_version=to_version,
                changelog=changelog[:10000]  # Limit changelog length
            )

            # Call LLM
            response = await self._call_llm(model, prompt)

            if not response:
                # Try fallback model
                logger.warning(f"Primary model failed, trying fallback for {image_name}")
                response = await self._call_llm(self.model_fallback, prompt)

            if not response:
                return None

            # Parse response
            analysis = self._parse_response(response)

            if analysis:
                # Add metadata
                analysis["llm_model"] = model
                analysis["llm_provider"] = self._get_provider(model)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing changelog for {image_name}: {str(e)}")
            return None

    async def _call_llm(self, model: str, prompt: str) -> Optional[str]:
        """Call LLM via LiteLLM"""
        try:
            # Prepare API keys based on model
            api_key = None
            if "claude" in model or "anthropic" in model:
                api_key = settings.ANTHROPIC_API_KEY
            elif "gpt" in model or "openai" in model:
                api_key = settings.OPENAI_API_KEY
            elif "gemini" in model:
                api_key = settings.GEMINI_API_KEY

            # For Ollama, use custom base URL
            if "llama" in model or "ollama" in model:
                response = await acompletion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    api_base=settings.OLLAMA_BASE_URL,
                    temperature=0.1,
                    max_tokens=4000
                )
            else:
                response = await acompletion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=api_key,
                    temperature=0.1,
                    max_tokens=4000
                )

            # Extract content
            content = response.choices[0].message.content

            return content

        except Exception as e:
            logger.error(f"Error calling LLM {model}: {str(e)}")
            return None

    def _parse_response(self, response: str) -> Optional[Dict]:
        """Parse LLM response as JSON"""
        try:
            # Try to extract JSON from response
            # Sometimes LLMs wrap JSON in markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end]
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end]

            # Parse JSON
            data = json.loads(response.strip())

            # Validate required fields
            required_fields = ["executive_summary", "risk_level", "safe_to_auto_update", "has_breaking_changes"]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing required field in LLM response: {field}")
                    return None

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.debug(f"Response was: {response[:500]}")
            return None

    def _select_model(self, is_sensitive: bool) -> str:
        """Select appropriate model based on sensitivity"""
        if is_sensitive and self.use_local_for_sensitive:
            return self.model_local
        return self.model_primary

    def _get_provider(self, model: str) -> str:
        """Determine provider from model name"""
        if "claude" in model or "anthropic" in model:
            return "anthropic"
        elif "gpt" in model or "openai" in model:
            return "openai"
        elif "gemini" in model:
            return "gemini"
        elif "llama" in model or "ollama" in model:
            return "ollama"
        else:
            return "unknown"

    async def summarize_multiple_updates(self, updates: List[Dict]) -> Optional[str]:
        """Generate a summary of multiple pending updates"""
        try:
            # Prepare summary prompt
            updates_text = "\n".join([
                f"- {u['image_name']}: {u['from_version']} → {u['to_version']} ({u.get('risk_level', 'unknown')} risk)"
                for u in updates[:20]  # Limit to 20 updates
            ])

            prompt = f"""Please provide a concise executive summary of the following pending Docker container updates:

{updates_text}

Focus on:
1. Total number of updates
2. Distribution by risk level
3. Any critical or high-risk updates that need attention
4. General recommendation

Keep it brief (3-4 sentences)."""

            model = self.model_primary
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error summarizing updates: {str(e)}")
            return None

    async def analyze_breaking_change_detail(self, change_description: str) -> Optional[Dict]:
        """Deep analysis of a specific breaking change"""
        try:
            prompt = f"""Analyze this breaking change in detail:

{change_description}

Provide:
1. Severity assessment
2. Likely impact on running services
3. Specific migration steps
4. Testing recommendations
5. Estimated time to handle

Format as JSON with keys: severity, impact, migration_steps, testing, estimated_hours"""

            model = self.model_primary
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Error analyzing breaking change: {str(e)}")
            return None


# Global instance
llm_service = LLMService()
