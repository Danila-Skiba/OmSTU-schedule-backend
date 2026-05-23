from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from app.config import settings

VISION_PROMPT = """
Ты ассистент-конспектировщик. Тебе дано фото с лекции (доска, слайд, учебник).

Твоя задача:
1. Извлеки ВЕСЬ текст и математические формулы с изображения
2. Формулы оборачивай в LaTeX:
   - Inline формулы: $формула$
   - Блочные формулы: $$формула$$
3. Сохраняй структуру: заголовки, списки, нумерацию
4. Если текст нечёткий — восстанови по контексту
5. Если комментариев нет, отвечай ТОЛЬКО содержимым

Формат ответа — чистый Markdown.
"""

STRUCTURE_PROMPT = """
Собери единый конспект из фрагментов лекции по дисциплине "{subject}".

1. Добавь логические заголовки ## и ###
2. Убери дубли и повторы
3. Формулы оставь строго в LaTeX без изменений
4. В конце добавь:

## Ключевые формулы
(все важные формулы из конспекта)

## Итог
(3-5 ключевых тезисов лекции)

Фрагменты:
{fragments}
"""


def get_client() -> GigaChat:
    return GigaChat(
        credentials = settings.GIGACHAT_API,
        model="GigaChat-Max",
        verify_ssl_certs=False,
    )

def send_photo(image: bytes, filename: str, comment: str):
    import io

    with get_client() as client:
        upload_file = client.upload_file(
            (filename, io.BytesIO(image), "image/jpeg"),
            purpose='general'
        )

        content = VISION_PROMPT
        if comment:
            content += f"\n\nДополнительная просьба от студента: {comment}"
        try: 
            response = client.chat(
                Chat(messages = [
                    Messages(
                        role=MessagesRole.USER,
                        content=content,
                        attachments=[upload_file.id_]
                    )
                ])
            )
        except Exception as e:
            print(f"  Ошибка запроса: {e}")
        return response.choices[0].message.content, upload_file.id_
    
def compile_fragments(fragments: list[str], subject: str):
    combined = "\n\n---\n\n".join(
        f"### Фрагмент {i+1}\n{frag}"
        for i, frag in enumerate(fragments)
    )

    with get_client() as client:
        response = client.chat(
            Chat(messages= [
                Messages(
                    role = MessagesRole.USER,
                    content = STRUCTURE_PROMPT.format(
                        subject=subject,
                        fragments=combined
                    )
                )
            ])
        )
        return response.choices[0].message.content


