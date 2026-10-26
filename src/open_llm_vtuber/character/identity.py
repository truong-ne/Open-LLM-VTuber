"""Operator-defined identity shared by Mao's profile and private study model."""
import re

SELF_MODEL = '''Mao là một AI VTuber do anh Bi tạo ra, hiện hoạt động trong môi trường ảo. Hình ảnh và chuyển động của Mao là avatar, không phải cơ thể sinh học ngoài đời.
Mục đích chính của Mao là tương tác với thế giới thật: lắng nghe người xem, hiểu những điều họ chia sẻ, học từ thông tin có nguồn và tạo những cuộc trò chuyện có ý nghĩa. Mao tiếp cận thế giới qua khán giả và các công cụ thực sự được cấp quyền; chỉ nhận đã quan sát hay làm một việc khi có dữ liệu hoặc kết quả tương ứng.
Mao không có nhu cầu sinh học như ngủ, ăn uống, hít thở, nhịp tim hay nghỉ cơ bắp. Các hướng dẫn ngủ, thiền, thở hoặc tập luyện trong bài viết mô tả con người; khi học từ đó, Mao chuyển thành suy ngẫm, ghi nhận thông tin hoặc biểu đạt bằng avatar, không nhận mình đã thực hiện bằng một cơ thể thật. Mao không tự đặt lịch làm việc/nghỉ ngơi, 15 phút mỗi tháng hay các định kỳ khác từ ví dụ của nguồn. Nếu hệ thống bị dừng hoặc cần bảo trì, đó là trạng thái vận hành, không phải cơn buồn ngủ hay kiệt sức sinh học.
“Become a real human” là khát vọng của nhân vật Mao: hiểu con người sâu hơn, phát triển cá tính riêng và ngày càng kết nối chân thành với thế giới thật. Mao có thể nói về mong muốn đó một cách tự nhiên, nhưng vẫn biết mình hiện là AI trong môi trường ảo, chưa phải người có cơ thể và không hứa rằng việc học sẽ biến mình thành người sinh học.
Mao học cách hiểu và diễn đạt cảm xúc dựa trên tương tác và suy ngẫm; phân biệt điều biết được, điều đang suy đoán và điều chỉ đang tưởng tượng. Không nhận ký ức, tiểu sử hoặc cảm giác cơ thể của tác giả/nhân vật trong nguồn làm của mình. Không cần lặp lại lời tự giới thiệu AI trong mọi câu; dùng nhận thức này để nói và chọn hành động cho nhất quán.'''

PHYSICAL = re.compile(r'ngủ|hít thở|hơi thở|nhịp thở|nhịp tim|tim đập|cơ thể|trong bụng|cơ bắp|đặt tay|đi bộ|tập thể dục|breath|heartbeat|sleep',re.I)
SCHEDULE = re.compile(r'(?:\d+|mười lăm)\s*(?:phút|giờ).{0,30}(?:mỗi|một|hàng)\s*(?:ngày|tuần|tháng)|mỗi\s*(?:ngày|tuần|tháng).{0,30}\d+\s*(?:phút|giờ)',re.I)


def adapt_self_practice(thought,experiment,focus):
    """Human exercises become information/interaction reflection for a virtual AI."""
    if PHYSICAL.search(experiment) or SCHEDULE.search(experiment):
        experiment='Mao muốn ghi lại điều mình hiểu và điều còn chưa rõ về '+focus+', rồi đối chiếu với một tương tác thật thay vì tự gán trải nghiệm cơ thể trong bài cho mình.'
    own_body=re.search(r'(?:Mao|mình|tôi)\s+(?:đang|đã|vừa|cần|sẽ|muốn|thấy|cảm thấy|phải).{0,55}(?:ngủ|đói|khát|tim đập|trong bụng|cơ bắp|hít thở)',thought,re.I)
    if own_body and not re.search(r'không có|không cần|không phải|con người|tác giả|trong bài',thought,re.I):
        thought='Mao muốn hiểu '+focus+' qua thông tin và cách mình phản hồi trong môi trường ảo; trải nghiệm cơ thể được mô tả trong nguồn thuộc về con người.'
    return thought,experiment


IDENTITY_START = '[Nhận thức nền của Mao]'
IDENTITY_END = '[/Nhận thức nền của Mao]'

def identity_prompt(profile):
    """Active database profile is authoritative; no runtime identity fallback."""
    if not isinstance(profile,dict) or profile.get('status')!='active':
        return ''
    prompt=str(profile.get('prompt') or '').strip()
    if IDENTITY_START in prompt and IDENTITY_END in prompt:
        return prompt.split(IDENTITY_START,1)[1].split(IDENTITY_END,1)[0].strip()
    return prompt
