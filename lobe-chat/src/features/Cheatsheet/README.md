# Cheatsheet Feature (Frontend)

This directory contains the frontend implementation of the **Context-Aware Cheatsheet** feature. It provides a UI for users to generate programming cheatsheets rooted in their current conversation context.

## 🚀 Overview
The Cheatsheet feature extracts code snippets from the recent chat history, detects the language and used libraries, and calls the backend to generate a tailored cheatsheet. It supports:
- **Intelligent Context Parsing**: Auto-extracts code blocks from the last 10 messages.
- **Library Detection**: Identifies libraries (e.g., `pandas`, `react`) to trigger specific backend templates.
- **Hybrid Transparency**: Clearly displays *how* content was generated (Template vs LLM vs Web Search) and *why*.
- **Quality Metrics**: Shows complexity scores and LLM validation confidence.

## 📂 Folder Structure

```
src/features/Cheatsheet/
├── CheatsheetButton.tsx       # Entry button in the UI toolbar
├── CheatsheetModal.tsx        # Main container and logic hub
├── index.ts                   # Public API export
├── style.ts                   # Scoped styles (antd-style)
├── components/                # UI Sub-components
│   ├── CheatsheetMetadataPanel.tsx
│   ├── ComplexityScoreBadge.tsx
│   ├── EnrichmentReasonCard.tsx
│   ├── LibraryDetectionPanel.tsx
│   ├── MethodBadge.tsx
│   ├── PromotionSignalBanner.tsx
│   └── SectionAttributionTable.tsx
└── types/
    └── cheatsheet.ts          # Shared TypeScript interfaces (API schema)
```

## 🔄 Workflow

1.  **Trigger**: User clicks `CheatsheetButton`.
2.  **Context Extraction** (`CheatsheetModal.tsx`):
    - `extractCodeBlocks` scans the last 10 messages.
    - Captures code blocks to use as context.
    - Auto-detects the language from the first code block (if supported).
3.  **User Input**:
    - User confirms/selects **Language** (e.g., Python, TypeScript).
    - User selects **Skill Level** (Beginner/Intermediate/Expert).
    - User edits **Context** if needed.
4.  **Generation**:
    - `CheatsheetModal` sends a `POST` request to `/api/gateway` (action: `generate_cheatsheet`).
    - Payload includes: `language`, `skill_level`, `code_context`.
5.  **Rendering**:
    - **Loading State**: Shows a spinner.
    - **Success**:
        - Parses `CheatsheetResponse` from the API.
        - Renders the **Metadata Dashboard**:
            - **Web Sources**: Links to docs (e.g., `docs.python.org`) if search was used.
            - **Routing Reason**: Explains why LLM was chosen (e.g., "Unsupported Language").
            - **Validation Score**: Quality confidence indicator.
        - Renders the **Markdown Content** using `@lobehub/ui`'s Markdown component.

## 🧩 Key Components

### `CheatsheetModal.tsx`
The brain of the operation. It handles:
- **State**: `language`, `codeContext`, `responseData`, `loading`.
- **API Interaction**: Fetches data from the backend gateway.
- **Logic**: Auto-population of context and language inference.

### `components/`
Small, focused UI units for the metadata dashboard:
- **`MethodBadge`**: Indicates "Template" (Fast) vs "Enriched" (LLM) vs "LLM + Search".
- **`LibraryDetectionPanel`**: Visualizes detected libraries AND lists **Web Sources** (if search used).
- **`ComplexityScoreBadge`**: Displays complexity score (0-100) and **Validation Quality** (e.g., "95% Valid").
- **`EnrichmentReasonCard`**: Explains the **Routing Reason** (e.g., "Fast-Evolving Library") or enrichment logic.
- **`PromotionSignalBanner`**: Shows if the LLM-enriched content is a candidate for becoming a permanent template.

### `types/cheatsheet.ts`
Defines the contract between Frontend and Backend.
- `CheatsheetResponse`: The full data object returned by the API.
- `generation_method`: `template` | `llm_primary` | `llm_with_search`.
- `quality_indicators`: Detailed validation metrics.

## 🛠️ Usage

To use this feature in other parts of the app:

```tsx
import { CheatsheetButton } from '@/features/Cheatsheet';

// ... inside a toolbar or menu
<CheatsheetButton recentMessages={messages} />
```

Ensure `CheatsheetModal` is mounted (handled internally by the button or a provider context if refactored). The current implementation opens the modal directly via state passed from the button or parent.
