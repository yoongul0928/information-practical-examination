
let questionsData = {};
let currentData = null;
let allAnswersVisible = false;

// questions_list.json에서 파일 목록 동적으로 로드
async function loadQuestionsData() {
    try {
        const response = await fetch('questions_list.json');
        questionsData = await response.json();
        console.log('✅ 파일 목록 로드 완료:', questionsData);
    } catch (error) {
        console.error('❌ 파일 목록 로드 실패:', error);
        questionsData = {}; // 기본값
    }
}

// 초기화
async function init() {
    // 먼저 파일 목록 로드
    await loadQuestionsData();
    
    const yearSelect = document.getElementById('yearSelect');

    // 년도 옵션 추가
    Object.keys(questionsData).sort((a, b) => b - a).forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + '년';
        yearSelect.appendChild(option);
    });

    yearSelect.addEventListener('change', handleYearChange);
}

function handleYearChange(e) {
    const year = e.target.value;
    const roundSelect = document.getElementById('roundSelect');

    roundSelect.innerHTML = '<option value="">선택하세요</option>';

    if (!year) {
        roundSelect.disabled = true;
        return;
    }

    roundSelect.disabled = false;
    Object.keys(questionsData[year]).sort().forEach(round => {
        const option = document.createElement('option');
        option.value = round;
        option.textContent = round + '회';
        roundSelect.appendChild(option);
    });

    roundSelect.addEventListener('change', handleRoundChange);
}

function handleRoundChange(e) {
    const year = document.getElementById('yearSelect').value;
    const round = e.target.value;

    if (!round) {
        document.getElementById('content').innerHTML = '<div class="empty-state"><h2>문제를 선택해주세요</h2></div>';
        document.getElementById('toggleAnswersBtn').disabled = true;
        document.getElementById('printBtn').disabled = true;
        return;
    }

    loadQuestions(year, round);
}

async function loadQuestions(year, round) {
    try {
        const filename = questionsData[year][round];
        const response = await fetch(filename);

        if (!response.ok) {
            throw new Error(`파일을 찾을 수 없습니다: ${filename}`);
        }

        currentData = await response.json();
        renderQuestions();
        document.getElementById('toggleAnswersBtn').disabled = false;
        document.getElementById('printBtn').disabled = false;
        allAnswersVisible = false;
        document.getElementById('toggleAnswersBtn').textContent = '정답 보기';
    } catch (error) {
        document.getElementById('content').innerHTML = `
                <div class="empty-state">
                    <h2>오류 발생</h2>
                    <p>${error.message}</p>
                </div>
            `;
    }
}

function renderQuestions() {
    const questions = currentData.questions;
    let html = `
            <div class="stats">
                총 <strong>${questions.length}</strong>개의 문제가 있습니다. (크롤링: ${currentData.metadata.crawl_time})
            </div>
        `;

    questions.forEach(q => {
        html += `
                <div class="question-card">
                    <div class="question-number">문제 ${q.number}</div>
                    <div class="question-text">${escapeHtml(q.text)}</div>
                    
                    ${q.images && q.images.length > 0 ? `
                        <div class="question-images">
                            ${q.images.map(img => `<img src="${img}" alt="문제 이미지" onerror="this.style.display='none'">`).join('')}
                        </div>
                    ` : ''}

                    ${q.options ? `
                        <div class="question-options">${escapeHtml(q.options)}</div>
                    ` : ''}

                    ${q.code_html ? `
                        <div class="question-code question-code-html">${q.code_html}</div>
                    ` : q.code ? `
                        <pre class="question-code"><code>${escapeHtml(q.code)}</code></pre>
                    ` : ''}

                    <button class="toggle-answer-btn" onclick="toggleAnswer(this)">정답 보기</button>
                    <div class="question-answer">
                        <div class="answer-label">✓ 정답</div>
                        <div class="answer-text">${escapeHtml(q.answer)}</div>
                    </div>
                </div>
            `;
    });

    document.getElementById('content').innerHTML = html;
}

function toggleAnswer(btn) {
    const answerDiv = btn.nextElementSibling;
    answerDiv.classList.toggle('show');
    btn.textContent = answerDiv.classList.contains('show') ? '정답 숨기기' : '정답 보기';
}

function toggleAllAnswers() {
    const answerDivs = document.querySelectorAll('.question-answer');
    const toggleBtns = document.querySelectorAll('.toggle-answer-btn');

    allAnswersVisible = !allAnswersVisible;

    answerDivs.forEach(div => {
        if (allAnswersVisible) {
            div.classList.add('show');
        } else {
            div.classList.remove('show');
        }
    });

    toggleBtns.forEach(btn => {
        btn.textContent = allAnswersVisible ? '정답 숨기기' : '정답 보기';
    });

    document.getElementById('toggleAnswersBtn').textContent =
        allAnswersVisible ? '정답 숨기기' : '정답 보기';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', init);
