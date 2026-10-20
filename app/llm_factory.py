from __future__ import annotations
import json
import logging
import os
import re
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger('llm_factory')
T = TypeVar('T', bound=BaseModel)

def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')

    if deepseek_key and (not openai_key or openai_key.startswith('tu_')):
        model = os.getenv('MODEL_NAME', 'deepseek-chat')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')
        return ChatOpenAI(
            api_key=deepseek_key,
            model=model,
            base_url=base_url,
            temperature=temperature,
        )

    base_url = os.getenv('OPENAI_BASE_URL')
    model = os.getenv('MODEL_NAME', 'gpt-4o-mini')
    kwargs = {'temperature': temperature, 'model': model}
    if base_url:
        kwargs['base_url'] = base_url
    if deepseek_key and (not openai_key or 'deepseek' in model.lower()):
        kwargs['api_key'] = deepseek_key
    elif openai_key:
        kwargs['api_key'] = openai_key

    return ChatOpenAI(**kwargs)

async def invoke_structured(llm: ChatOpenAI, schema_cls: Type[T], messages: list[BaseMessage]) -> T:
    schema_json = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
    instruction = (
        '\n\n[INSTRUCCION DE FORMATO OBLIGATORIA]:\n'
        'Debes responder UNICAMENTE con un objeto JSON valido que coincida exactamente con este esquema Pydantic:\n'
        + schema_json + '\n'
        '- NO agregues texto explicativo fuera del JSON.'
    )

    augmented_messages = list(messages)
    if augmented_messages and isinstance(augmented_messages[-1], HumanMessage):
        augmented_messages[-1] = HumanMessage(content=str(augmented_messages[-1].content) + instruction)
    else:
        augmented_messages.append(HumanMessage(content=instruction))

    response = await llm.ainvoke(augmented_messages)
    content = response.content if isinstance(response.content, str) else str(response.content)

    cleaned = content.strip()
    if cleaned.startswith('`'):
        cleaned = re.sub(r'^`(?:json)?', '', cleaned, flags=re.IGNORECASE).strip()
    if cleaned.endswith('`'):
        cleaned = re.sub(r'`$', '', cleaned).strip()

    try:
        data = json.loads(cleaned)
        return schema_cls.model_validate(data)
    except Exception as e:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            data = json.loads(match.group(0))
            return schema_cls.model_validate(data)
        raise e
