"""User-facing text produced by deterministic code (not the LLM), in both languages.

These messages must be correct even when the LLM is down, so they are static,
reviewed text rather than generated text.
"""

EMERGENCY_REPLY = {
    "en": (
        "Your symptoms may be a medical emergency. Please call 997 (Saudi Red Crescent "
        "ambulance) now; 911 also works in Saudi Arabia. Do not drive yourself. If you can, "
        "stay where you are, unlock the door, and have someone stay with you. The nearest "
        "emergency departments in our directory are listed below."
    ),
    "ar": (
        "قد تكون أعراضك حالة طبية طارئة. يرجى الاتصال الآن على 997 (إسعاف الهلال الأحمر "
        "السعودي)، ويعمل الرقم 911 أيضًا في المملكة. لا تقد السيارة بنفسك. إن أمكن، ابقَ في "
        "مكانك وافتح الباب واطلب من أحد البقاء معك. أقرب أقسام الطوارئ في دليلنا موضحة أدناه."
    ),
}

FALLBACK_REPLY = {
    "en": (
        "Sorry, I can't complete your request right now because of a technical problem. "
        "If you have severe or worsening symptoms, such as chest pain with shortness of "
        "breath, sweating or fainting, call 997 immediately. Otherwise, please try again in "
        "a moment."
    ),
    "ar": (
        "عذرًا، لا أستطيع إكمال طلبك الآن بسبب مشكلة تقنية. إذا كانت لديك أعراض شديدة أو "
        "تزداد سوءًا، مثل ألم في الصدر مع ضيق في التنفس أو تعرق أو إغماء، فاتصل فورًا على 997. "
        "وإلا فيرجى المحاولة مرة أخرى بعد قليل."
    ),
}

NO_VERIFIED_MATCH = {
    "en": (
        "I couldn't find a verified match in our provider directory for this request, so "
        "I'm not recommending a specific doctor. You can try another city, or ask me to "
        "search a related specialty."
    ),
    "ar": (
        "لم أجد مطابقة موثّقة في دليل مقدمي الخدمة لهذا الطلب، لذلك لن أرشّح طبيبًا محددًا. "
        "يمكنك تجربة مدينة أخرى أو أن تطلب مني البحث في تخصص قريب."
    ),
}

BEST_GUIDANCE_NOTE = {
    "en": (
        "Based on what you've shared so far, my best guidance is to book a visit with a "
        "specialist soon. If symptoms get worse, call 997."
    ),
    "ar": (
        "بناءً على ما ذكرته حتى الآن، أنصحك بحجز موعد قريب مع طبيب مختص. إذا ساءت الأعراض "
        "فاتصل على 997."
    ),
}

DISCLAIMER = {
    "en": (
        "HealTrip's assistant gives navigation guidance, not medical advice or a diagnosis. "
        "In an emergency call 997."
    ),
    "ar": (
        "يقدّم مساعد هيل تريب إرشادات للتوجيه فقط، وليس نصيحة طبية أو تشخيصًا. في الحالات "
        "الطارئة اتصل على 997."
    ),
}
