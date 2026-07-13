import edge_tts


async def create_voice(text):

    communicate = edge_tts.Communicate(
        text,
        "zh-CN-XiaoxiaoNeural"
    )

    await communicate.save("voice.mp3")


async def text_to_speech(text):
    await create_voice(text)