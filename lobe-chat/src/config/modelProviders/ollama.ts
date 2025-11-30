import { ModelProviderCard } from '@/types/llm';

const Ollama: ModelProviderCard = {
  chatModels: [
    {
      id: 'deepseek-r1',
      displayName: 'DeepSeek R1',
      description: 'DeepSeek reasoning model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'deepseek-r1:8b',
      displayName: 'DeepSeek R1 8B',
      description: 'Efficient reasoning model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'gpt-oss:20b-cloud',
      displayName: 'GPT-OSS 20B (Cloud)',
      description: 'Open-source GPT model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'gpt-oss:120b-cloud',
      displayName: 'GPT-OSS 120B (Cloud)',
      description: 'Large GPT-OSS model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'qwen3:4b',
      displayName: 'Qwen3 4B',
      description: 'Qwen3 lightweight model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'qwen3-coder:480b-cloud',
      displayName: 'Qwen3 Coder 480B (Cloud)',
      description: 'Qwen3 Coder model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'deepseek-v3.1:671b-cloud',
      displayName: 'DeepSeek V3.1 671B (Cloud)',
      description: 'DeepSeek ultra large model with tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true
    },
    {
      id: 'qwen3-vl:235b-cloud',
      displayName: 'Qwen3-VL 235B (Cloud)',
      description: 'Vision-language model with vision + tool-calling support.',
      contextWindowTokens: 128_000,
      enabled: true,
      functionCall: true,
      vision: true
    },
    {
      id: 'gemma3:1b',
      displayName: 'Gemma3 1B',
      description: 'Google Gemma3 small model.',
      contextWindowTokens: 32_768,
      enabled: true
    }
  ],

  checkModel: 'deepseek-r1',

  defaultShowBrowserRequest: true,

  description:
    'Clean Ollama provider configuration with only user-selected models and tool-calling support.',

  id: 'ollama',

  modelList: { showModelFetcher: true },

  modelsUrl: 'https://ollama.com/library',

  name: 'Ollama',

  settings: {
    defaultShowBrowserRequest: true,
    sdkType: 'ollama',
    showApiKey: false,
    showModelFetcher: true
  },

  showApiKey: false,
  url: 'https://ollama.com',
};

export default Ollama;
