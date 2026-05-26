---

## 기존 UI

### Graphologue

User 개입도 작은 편

하나의 프롬프트를 이해하기 쉽게 그래프로 표현함. 노드는 키워드 단위임.

- GPT-4가 각 entity(키워드)에게 ID를 부여. coreference하는 entity끼리 같은 부류의 ID로 분류됨.
- 하나의 response를 같은 측면을 가진 여러 문단으로 나눠 각 문단의 entity를 그래프로 표현함.

하나를 ‘분석’하기 위해 여러개로 쪼개는 느낌

→ 우리는 전체 thread를 한 눈에 보기 위해 프롬프트 단위로 나누는 느낌. 우리 거가 훨씬 쉬울 것 같다.

---

### Sensecape

User의 개입도가 큰 편

캔버스에서 노드부터 만들고 그 다음에 질의응답을 하는 구조. 우리랑 역순

- **semantic zoom:**
    
    내용이 너무 많아서 눈이 돌아가면 zoom out하면 내용을 키워드 단위로 간소화하기.
    
    → 우리도 노드를 이런식으로 줄여도 되겠다.
    

- **Hierarchical exploration**
    
    → 노드들이 너무 많아서 복잡해지면 이런 3차원 뷰로 연관성이 적거나 안에서 새로운 주제를 시작하는 노드를 parent로 빼서 새로운 canvas에 옮길 수 있겠다.
    


---

## 구현

### 알고리즘

```markdown
LOOP per QA turn:
  1. Summarize(Q, A) <- 질의응답용 AI
  2. Re-infer all node relations 
  3. Add node to graph
  4. Update edge types & weights
  5. Render updated graph
 2~4번은 그래프 구축용 AI
```

턴 단위로 노드를 생성하면 노드가 너무 많아져서 그래프가 복잡해질 수 있음.

### 노드 인터페이스 구성

노드 이름: user의 질문 요약본

노드의 내용: user의 질문에 대한 AI의 답변

### 엣지 종류 구성

- elaboration
- ~~contrast~~   ← 채팅 기반 AI에서는 이거 별로 안썼던 것 같음.
- causality
- evidence
- ~~emotional_trigger~~
- ~~topic_cluster~~: edge로 구분하는게 아니라 물리적인 거리를 가까이

![image.png](attachment:2b5c59e5-0a68-49bb-b6f9-c51822ee0144:image.png)

#### 의구점

1. 자식 노드들끼리 이으면 더 복잡해보이지 않을까?
    
    → 트리구조로
    
2. 과연 edge의 종류를 기입하는게 도움이 될 것인가? 인지적 부담만 커지는 것 아닐까?
    
    엣지 종류 특정 x
    
    LLM에게 엣지에 들어갈 키워드 출력 
    

---

## 회의 내용

사용자 주도형 인터페이스 구성을 어떻게 할 것인가?

### LLM usage

질의응답, 엣지구성, 요약

### User study

- nasa tlx
이걸로만 평가해도 충분할 듯
- user task
주제 정도만 정해주고 우리가 만든 UI 사용해보게 시키기

### **benchmark**

기존 채팅 AI에게 물어봤던 것들 인당 3개 정도 복잡한 스레드 찾아서 2개 3개 추려서 테스트