import asyncio
from groq import AsyncGroq

async def main():
    ag = AsyncGroq(api_key='fake')
    stream_cm = ag.with_streaming_response.chat.completions.create(
        model='x',
        messages=[{'role': 'user', 'content': 'hi'}],
        stream=True,
    )
    print('stream_cm type', type(stream_cm))
    print('stream_cm has __aiter__', hasattr(stream_cm, '__aiter__'))
    print('stream_cm has __aenter__', hasattr(stream_cm, '__aenter__'))
    response = await stream_cm.__aenter__()
    print('response type', type(response))
    print('response has __aiter__', hasattr(response, '__aiter__'))
    print('response has __aenter__', hasattr(response, '__aenter__'))
    print('response has iter_lines', hasattr(response, 'iter_lines'))
    await stream_cm.__aexit__(None, None, None)

asyncio.run(main())
