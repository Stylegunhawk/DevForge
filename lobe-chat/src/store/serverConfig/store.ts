import { StoreApiWithSelector } from '@lobechat/types';
import { StoreApi } from 'zustand';
import { createContext } from 'zustand-utils';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';
import { StateCreator } from 'zustand/vanilla';

import {
  DEFAULT_FEATURE_FLAGS,
  IFeatureFlagsState,
  mapFeatureFlagsEnvToState,
} from '@/config/featureFlags';
import { createDevtools } from '@/store/middleware/createDevtools';
import { GlobalServerConfig } from '@/types/serverConfig';
import { merge } from '@/utils/merge';

import { ServerConfigAction, createServerConfigSlice } from './action';

interface ServerConfigState {
  featureFlags: IFeatureFlagsState;
  isMobile?: boolean;
  segmentVariants?: string;
  serverConfig: GlobalServerConfig;
}

const initialState: ServerConfigState = {
  featureFlags: mapFeatureFlagsEnvToState(DEFAULT_FEATURE_FLAGS),
  segmentVariants: '',
  serverConfig: { aiProvider: {}, telemetry: {} },
};

//  ===============  聚合 createStoreFn ============ //

export interface ServerConfigStore extends ServerConfigState, ServerConfigAction { }

type CreateStore = (
  initState: Partial<ServerConfigStore>,
) => StateCreator<ServerConfigStore, [['zustand/devtools', never]]>;

const createStore: CreateStore =
  (runtimeState) =>
    (...params) => {
      // 1. Perform the standard merge
      const mergedState = merge(initialState, runtimeState);

      // 2. 🔓 DEVFORGE HACK: Conditional Override
      // Only apply this hack if your custom RAG mode is enabled in .env
      if (process.env.NEXT_PUBLIC_USE_CUSTOM_RAG === 'true') {
        mergedState.featureFlags = {
          ...mergedState.featureFlags,
          enableFileUpload: true,
          enableKnowledgeBase: true,
        };
      }

      // 3. Return the state
      return {
        ...mergedState,
        ...createServerConfigSlice(...params),
      };
    };

//  ===============  实装 useStore ============ //

let store: StoreApi<ServerConfigStore>;

declare global {
  interface Window {
    global_serverConfigStore: StoreApi<ServerConfigStore>;
  }
}

const devtools = createDevtools('serverConfig');

export const initServerConfigStore = (initState: Partial<ServerConfigStore>) =>
  createWithEqualityFn<ServerConfigStore>()(devtools(createStore(initState || {})), shallow);

export const createServerConfigStore = (initState?: Partial<ServerConfigStore>) => {
  // make sure there is only one store
  if (!store) {
    store = createWithEqualityFn<ServerConfigStore>()(
      devtools(createStore(initState || {})),
      shallow,
    );

    if (typeof window !== 'undefined') {
      window.global_serverConfigStore = store;
    }
  }

  return store;
};

export const { useStore: useServerConfigStore, Provider } =
  createContext<StoreApiWithSelector<ServerConfigStore>>();
