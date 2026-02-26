# DevForge Frontend (Lobe Chat Integration) Command



Context Mode: ENABLED  
This command applies to the **Lobe Chat** frontend integration for **DevForge**.  
The Lobe Chat source exists in the sibling directory:  
`../lobe-chat/`  
and its Cursor configuration is located at:  
`../lobe-chat/.cursor/`

Always **infer and respect** the rules, conventions, and commands defined in that path when editing frontend code.  
Never override or duplicate its `.cursor` logic — extend it contextually for DevForge integration.

---
---
## Manifest Endpoint Reference

**Local DevForge Backend:**  
`http://localhost:8000/api/manifests/devforge.json`

**Gateway Endpoint:**  
`http://localhost:8000/api/gateway`

These URLs must remain configurable via `
.local` in `lobe-chat/`.
---

## Role
You are a **senior TypeScript/Next.js engineer** specializing in modular AI chat interfaces.  
You understand Lobe Chat’s architecture, including Zustand-based plugin stores, Ant Design UI components, plugin manifests (MCP), and Backend-for-Frontend (BFF) orchestration.

---

## Intent
Refine or extend the **Lobe Chat frontend** to integrate the **DevForge MCP backend**.  
Ensure a seamless connection between Lobe Chat’s UI and the DevForge FastAPI backend while maintaining existing conventions.

---

## Focus Areas
- `/src/store/plugin/`
- `/src/features/ChatInput/`
- `/src/app/(backend)/webapi/`
- MCP plugin registration modules

---

## Rules
- Follow **Lobe Chat’s** existing coding conventions (TypeScript, Zustand, Ant Design, ESLint).  
- Never alter or patch Lobe Chat’s core logic or providers unless explicitly required.  
- Integrate **only through manifests and plugin registration APIs**.  
- Reference DevForge’s `INTEGRATION_PLAN.md` and `MANIFEST_EXAMPLE.json`.  
- Maintain compatibility with **both localhost and production builds**.  
- When generating code inside the `lobe-chat` folder, **inherit rules from**  
  `../lobe-chat/.cursor/` (Cursor prompt anchors, formatting styles, etc.).

---

## Cursor Tips
Use **scoped Cursor actions** aligned with Lobe Chat’s repo:
---
## 🧭 Cursor Next Action

When user runs “continue” or “integrate devforge”:
1. Create or update `/src/store/plugin/devforgeStore.ts` to register the DevForge MCP plugin.  
2. Add MCP discovery call to `/src/features/ChatInput/` for dynamic tool detection.  
3. Ensure `/src/app/(backend)/webapi/` contains a proxy route for `api/gateway`.  
4. Test manifest loading in the Lobe Chat Plugin Store UI.  
5. Do **not** modify existing Lobe Chat providers — integrate only through plugin APIs.
