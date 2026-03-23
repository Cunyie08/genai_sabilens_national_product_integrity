import sys
sys.path.insert(0, 'C:/Dev/sabilens/ai_engine')
sys.path.insert(0, 'C:/Dev/sabilens/ai_engine/visual')
from ai_engine.agent.verification_agent import NAFDACVerificationAgent
a = NAFDACVerificationAgent()
r = a.retriever
from ai_engine.ocr_linguistic.extractor import extract_nafdac_number, extract_text_blocks, build_raw_text
blocks = extract_text_blocks(r'C:/Dev/sabilens/ai_engine/visual/test_images/kelloggs_cornflakes_300g+45g_left.jpg')
raw = build_raw_text(blocks)
print('strict:', extract_nafdac_number(raw, None))
print('with retriever:', extract_nafdac_number(raw, r))