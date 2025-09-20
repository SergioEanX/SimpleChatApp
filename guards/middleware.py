"""
Guardrails Middleware - Improved async and stream handling
========================================================
"""

import json
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from typing import Optional, Callable, Awaitable, AsyncGenerator

from guardrails import Guard

from .config import load_config, PROTECTED_ENDPOINTS
from .validators import create_input_guard, create_output_guard
from .custom import add_topic_restriction
from .messages import get_violation_message, create_response_body
from .utils import extract_query_from_request, extract_content_from_response, should_validate_input

logger = logging.getLogger(__name__)

class GuardrailsMiddleware(BaseHTTPMiddleware):
    """Guardrails Middleware with improved async/stream handling"""

    def __init__(self, app):
        super().__init__(app)
        logger.info("🚀 GuardrailsMiddleware __init__ started")
        
        self.config = load_config()
        logger.info(f"📋 Config loaded: topic_restriction={self.config.get('enable_topic_restriction')}, pii_detection={self.config.get('enable_pii_detection')}")
        
        # Create base guards
        self.input_guard = create_input_guard(self.config)
        self.output_guard = create_output_guard(self.config)
        logger.info(f"🛡️ Base guards created: input_validators={len(self.input_guard.validators) if hasattr(self.input_guard, 'validators') else 0}")
        
        # Add topic restriction if enabled
        if self.config.get("enable_topic_restriction", False):
            logger.info("🔄 Attempting to add topic restriction...")
            try:
                topic_guard = add_topic_restriction(self.config)
                if topic_guard and hasattr(topic_guard, 'validators') and topic_guard.validators:
                    all_validators = list(self.input_guard.validators) + list(topic_guard.validators)
                    self.input_guard = Guard().use_many(*all_validators)
                    logger.info(f"✅ Topic restriction enabled with {len(topic_guard.validators)} validators")
                else:
                    logger.warning("⚠️ Topic guard created but has no validators")
            except Exception as e:
                logger.warning(f"❌ Failed to add topic restriction: {e}")
        else:
            logger.info("ℹ️ Topic restriction disabled in configuration")
        
        self.endpoints = PROTECTED_ENDPOINTS
        logger.info("✅ GuardrailsMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Main dispatch with improved error handling"""
        
        logger.info(f"🔍 Middleware dispatch called for: {request.method} {request.url.path}")
        
        # Skip non-protected endpoints
        if not self._is_protected_endpoint(request.url.path):
            logger.info(f"⚡ Endpoint {request.url.path} not protected, skipping validation")
            return await call_next(request)
        
        logger.info(f"🛡️ Endpoint {request.url.path} is protected, applying validation")

        try:
            # Input validation
            if should_validate_input(request.url.path, self.endpoints):
                modified_request, violation = await self._validate_and_modify_input(request)
                if violation:
                    return violation
                request = modified_request or request

            # Process request
            response = await call_next(request)

            # Output validation for successful responses
            if response.status_code == 200:
                validated_response = await self._validate_output(response)
                return validated_response or response

            return response

        except Exception as e:
            logger.error(f"Middleware error for {request.url.path}: {e}")
            return await call_next(request)  # Graceful fallback

    def _is_protected_endpoint(self, path: str) -> bool:
        """Check if endpoint is protected (improved path matching)"""
        for endpoint in self.endpoints:
            if path == endpoint:
                return True
            # Handle parameterized paths like /conversation/{thread_id}/history
            if '{' in endpoint:
                endpoint_pattern = endpoint.replace('{thread_id}', '[^/]+')
                import re
                if re.match(f'^{endpoint_pattern}$', path):
                    return True
        return False

    async def _validate_and_modify_input(self, request: Request) -> tuple[Optional[Request], Optional[JSONResponse]]:
        """Validate input and return modified request if needed"""
        
        if request.method != "POST":
            return None, None

        try:
            # Read body only once to avoid consumption issues
            body_bytes = await request.body()
            if not body_bytes:
                return None, None

            # Parse JSON
            try:
                data = json.loads(body_bytes.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                error_msg = f"Invalid JSON or encoding: {e}"
                return None, JSONResponse(
                    status_code=400,
                    content=create_response_body(error_msg, "format_error")
                )

            # Extract and validate query
            query = extract_query_from_request(data)
            if not query:
                return None, None

            # Apply guards validation
            try:
                logger.info(f"🔄 About to validate with input_guard containing {len(self.input_guard.validators)} validators")
                for i, validator in enumerate(self.input_guard.validators):
                    logger.info(f"🔍 Validator {i}: {validator.id} - on_fail is: {validator.on_fail}")
                
                logger.info(f"🎯 Validating query: '{query[:50]}...'")
                
                # Run validation and catch specific validator failures
                outcome = self.input_guard.validate(query)
                logger.info(f"✅ Validation completed successfully")
                
                # Check if content was modified (sanitized)
                if outcome.validated_output != query:
                    logger.info(f"Input sanitized: '{query[:50]}...' -> '{outcome.validated_output[:50]}...'")
                    
                    # Create new request with modified body
                    data["query"] = outcome.validated_output
                    new_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                    
                    # Create new receive callable for modified body
                    async def new_receive():
                        return {"type": "http.request", "body": new_body, "more_body": False}
                    
                    # Create new request with modified body
                    new_request = Request(request.scope, receive=new_receive)
                    return new_request, None

                return None, None  # No modification needed

            except Exception as e:
                # Validation failed - create violation response
                logger.error(f"🚫 VALIDATION FAILED - Exception type: {type(e).__name__}")
                logger.error(f"🚫 VALIDATION FAILED - Exception message: {str(e)}")
                logger.error(f"🚫 VALIDATION FAILED - Full exception: {repr(e)}")
                
                # Try to determine which validator failed
                error_message = str(e)
                if "dati personali sensibili" in error_message:
                    logger.error("🚫 FAILED VALIDATOR: ItalianPIIValidator")
                    violation_type = "pii_violation"
                elif "sistema AI per analytics" in error_message:
                    logger.error("🚫 FAILED VALIDATOR: LLMTopicValidator")
                    violation_type = "topic_violation"
                elif "toxic" in error_message.lower():
                    logger.error("🚫 FAILED VALIDATOR: ToxicLanguage")
                    violation_type = "toxic_violation"
                else:
                    logger.error("🚫 FAILED VALIDATOR: Unknown")
                    violation_type = "content_violation"
                
                message = get_violation_message(str(e), self.config)
                logger.warning(f"Input validation failed: {e}")
                
                return None, JSONResponse(
                    status_code=400,
                    content=create_response_body(message, violation_type)
                )

        except Exception as e:
            logger.error(f"Input validation error: {e}")
            return None, None  # Graceful fallback

    async def _validate_output(self, response: Response) -> Optional[Response]:
        """Validate and potentially modify output response"""
        
        try:
            # Handle different response types
            body_bytes = await self._extract_response_body(response)
            if not body_bytes:
                return None

            # Parse JSON response
            try:
                data = json.loads(body_bytes.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Non-JSON response, skip validation
                return None

            # Extract content for validation
            content = extract_content_from_response(data)
            if not content or not isinstance(content, str):
                return None

            # Apply output validation
            try:
                outcome = self.output_guard.validate(content)
                
                # Check if content was modified
                if outcome.validated_output != content:
                    logger.info(f"Output sanitized: '{content[:50]}...' -> '{outcome.validated_output[:50]}...'")
                    
                    # Update response data
                    data["result"] = outcome.validated_output
                    new_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                    
                    # Create new response with sanitized content
                    return Response(
                        content=new_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type or "application/json"
                    )

                return None  # No modification needed

            except Exception as e:
                # Output validation failed - log but don't block
                logger.warning(f"Output validation failed: {e}")
                return None  # Continue with original response

        except Exception as e:
            logger.error(f"Output validation error: {e}")
            return None  # Graceful fallback

    async def _extract_response_body(self, response: Response) -> Optional[bytes]:
        """Extract body from different response types"""
        
        try:
            if isinstance(response, StreamingResponse):
                # Handle streaming responses
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk)
                return b"".join(chunks)
            
            elif hasattr(response, 'body'):
                # Regular response with body attribute
                return response.body
            
            else:
                # Response without direct body access
                return None

        except Exception as e:
            logger.error(f"Failed to extract response body: {e}")
            return None