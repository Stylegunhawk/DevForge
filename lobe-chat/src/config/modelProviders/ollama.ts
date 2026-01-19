import { ModelProviderCard } from '@/types/llm';

const Ollama: ModelProviderCard = {
  chatModels: [
    {
      contextWindowTokens: 128_000,
      description: 'DeepSeek reasoning model with tool-calling support.',
      displayName: 'DeepSeek R1',
      enabled: true,
      functionCall: true,
      id: 'deepseek-r1',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Efficient reasoning model with tool-calling support.',
      displayName: 'DeepSeek R1 8B',
      enabled: true,
      functionCall: true,
      id: 'deepseek-r1:8b',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Open-source GPT model with tool-calling support.',
      displayName: 'GPT-OSS 20B (Cloud)',
      enabled: true,
      functionCall: true,
      //files: true,
      id: 'gpt-oss:20b-cloud',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Large GPT-OSS model with tool-calling support.',
      displayName: 'GPT-OSS 120B (Cloud)',
      enabled: true,
      files: true,
      functionCall: true,
      id: 'gpt-oss:120b-cloud',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Qwen3 lightweight model with tool-calling support.',
      displayName: 'Qwen3 4B',
      enabled: true,
      functionCall: true,
      id: 'qwen3:4b',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Qwen3 Coder model with tool-calling support.',
      displayName: 'Qwen3 Coder 480B (Cloud)',
      enabled: true,
      functionCall: true,
      //files: true,
      id: 'qwen3-coder:480b-cloud',
    },
    {
      contextWindowTokens: 128_000,
      description: 'DeepSeek ultra large model with tool-calling support.',
      displayName: 'DeepSeek V3.1 671B (Cloud)',
      enabled: true,
      functionCall: true,
      //files: true,
      id: 'deepseek-v3.1:671b-cloud',
    },
    {
      contextWindowTokens: 128_000,
      description: 'Vision-language model with vision + tool-calling support.',
      displayName: 'Qwen3-VL 235B (Cloud)',
      enabled: true,
      functionCall: true,
      //files: true,
      id: 'qwen3-vl:235b-cloud',
      vision: true,
    },
    {
      contextWindowTokens: 32_768,
      description: 'Google Gemma3 small model.',
      displayName: 'Gemma3 1B',
      enabled: true,
      id: 'gemma3:1b',
    },
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
    showModelFetcher: true,
  },

  showApiKey: false,
  url: 'https://ollama.com',
};

export default Ollama;
