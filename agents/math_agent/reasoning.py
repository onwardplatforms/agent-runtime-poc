"""Continuous reasoning support for the math agent.

This module provides the infrastructure for the math agent to engage in multi-step reasoning,
allowing it to "think out loud" during calculations and provide explanations
of its thought process.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages in the continuous reasoning flow."""

    REASONING = "reasoning"  # Intermediate reasoning/thinking
    CALCULATION = "calculation"  # Mathematical calculation
    RESPONSE = "response"    # Final response to user


class ReasoningStep:
    """Represents a step in the agent's reasoning process."""

    def __init__(
        self,
        message_type: MessageType,
        content: str,
        operation: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
    ):
        """Initialize a reasoning step.

        Args:
            message_type: Type of message (reasoning, calculation, response)
            content: The text content of the step
            operation: Name of the math operation (for calculations)
            inputs: Input parameters for the operation (for calculations)
            result: Result of the calculation (for calculations)
        """
        self.message_type = message_type
        self.content = content
        self.operation = operation
        self.inputs = inputs
        self.result = result

    def __str__(self) -> str:
        """Get string representation of the reasoning step."""
        if self.message_type == MessageType.CALCULATION:
            return f"CALCULATION: {self.operation}\nInputs: {self.inputs}\nResult: {self.result}"
        elif self.message_type == MessageType.REASONING:
            return f"REASONING: {self.content}"
        else:
            return f"RESPONSE: {self.content}"


class ReasoningChain:
    """Manages a sequence of reasoning steps for the math agent.

    This class tracks the agent's thinking process, calculations, and responses
    during a continuous reasoning session.
    """

    def __init__(self):
        """Initialize a new reasoning chain."""
        self.steps: List[ReasoningStep] = []
        self.current_reasoning = ""

    def add_reasoning(self, content: str) -> None:
        """Add a reasoning step to the chain.

        Args:
            content: The reasoning content to add
        """
        # If we have accumulated reasoning, create a step
        if self.current_reasoning:
            self.current_reasoning += "\n" + content
        else:
            self.current_reasoning = content

    def finalize_reasoning(self) -> None:
        """Finalize the current reasoning and add it as a step."""
        if self.current_reasoning:
            self.steps.append(
                ReasoningStep(
                    message_type=MessageType.REASONING,
                    content=self.current_reasoning,
                )
            )
            self.current_reasoning = ""

    def add_calculation(
        self, operation: str, inputs: Dict[str, Any], result: Any
    ) -> None:
        """Add a calculation step to the chain.

        Args:
            operation: Name of the math operation
            inputs: Input parameters for the operation
            result: Result of the calculation
        """
        # Finalize any accumulated reasoning first
        self.finalize_reasoning()
        
        self.steps.append(
            ReasoningStep(
                message_type=MessageType.CALCULATION,
                content=f"Performing {operation} with inputs {inputs}",
                operation=operation,
                inputs=inputs,
                result=result,
            )
        )

    def add_response(self, content: str) -> None:
        """Add a final response step to the chain.

        Args:
            content: The response content
        """
        # Finalize any accumulated reasoning first
        self.finalize_reasoning()
        
        self.steps.append(
            ReasoningStep(
                message_type=MessageType.RESPONSE,
                content=content,
            )
        )

    def get_formatted_chain(self) -> str:
        """Get a formatted representation of the entire reasoning chain.

        Returns:
            A string representation of the reasoning chain
        """
        result = []
        for step in self.steps:
            result.append(str(step))
        return "\n\n".join(result)

    def get_detailed_explanation(self) -> str:
        """Get a user-friendly detailed explanation of the reasoning process.

        Returns:
            A formatted explanation string suitable for end users
        """
        explanation_parts = []
        
        for step in self.steps:
            if step.message_type == MessageType.REASONING:
                explanation_parts.append(step.content)
            elif step.message_type == MessageType.CALCULATION:
                if step.operation == "add":
                    explanation_parts.append(f"Adding {step.inputs.get('a')} and {step.inputs.get('b')} gives {step.result}")
                elif step.operation == "subtract":
                    explanation_parts.append(f"Subtracting {step.inputs.get('b')} from {step.inputs.get('a')} gives {step.result}")
                elif step.operation == "multiply":
                    explanation_parts.append(f"Multiplying {step.inputs.get('a')} by {step.inputs.get('b')} gives {step.result}")
                elif step.operation == "divide":
                    explanation_parts.append(f"Dividing {step.inputs.get('a')} by {step.inputs.get('b')} gives {step.result}")
                elif step.operation == "square_root":
                    explanation_parts.append(f"The square root of {step.inputs.get('a')} is {step.result}")
                elif step.operation == "power":
                    explanation_parts.append(f"Raising {step.inputs.get('a')} to the power of {step.inputs.get('b')} gives {step.result}")
                elif step.operation == "percentage":
                    explanation_parts.append(f"{step.inputs.get('a')} is {step.result}% of {step.inputs.get('b')}")
                elif step.operation == "percentage_of":
                    explanation_parts.append(f"To calculate {step.inputs.get('percentage')}% of {step.inputs.get('value')}, I multiply {step.inputs.get('value')} by {step.inputs.get('percentage')}/100, which gives {step.result}")
                else:
                    explanation_parts.append(f"Performing {step.operation} with inputs {step.inputs} gives {step.result}")
            elif step.message_type == MessageType.RESPONSE:
                if explanation_parts:  # Only add "Therefore" if there are previous steps
                    explanation_parts.append(f"Therefore, {step.content}")
                else:
                    explanation_parts.append(step.content)
                
        return "\n".join(explanation_parts)

    def get_all_steps(self) -> List[ReasoningStep]:
        """Get all steps in the reasoning chain.

        Returns:
            List of all reasoning steps
        """
        return self.steps.copy() 