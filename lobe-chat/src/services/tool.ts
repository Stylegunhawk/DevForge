import { PluginQueryParams } from '@/types/discover';
import { convertOpenAIManifestToLobeManifest, getToolManifest } from '@/utils/toolManifest';

class ToolService {
  getOldPluginList = async (_params: PluginQueryParams): Promise<any> => {
    return {
      items: [],
      totalCount: 0,
      pageSize: 50,
      currentPage: 1,
      totalPages: 1,
    };
  };

  getToolManifest = getToolManifest;
  convertOpenAIManifestToLobeManifest = convertOpenAIManifestToLobeManifest;
}

export const toolService = new ToolService();
