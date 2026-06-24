import { ref, type Ref } from 'vue';

import { api } from '../../api/client';
import type { WorkspaceSummary } from '../../types';

export function useWorkspaceCatalog(errorMsg: Ref<string | null>) {
  const workspaces = ref<WorkspaceSummary[]>([]);
  const isWorkspacesLoading = ref(false);

  const loadWorkspaces = async () => {
    isWorkspacesLoading.value = true;
    try {
      workspaces.value = await api.getWorkspaces();
    } catch (err: any) {
      errorMsg.value = 'Failed to load workspaces: ' + err.message;
    } finally {
      isWorkspacesLoading.value = false;
    }
  };

  const selectWorkspaceDialog = async () => {
    try {
      errorMsg.value = null;
      const ws = await api.selectWorkspaceDialog();
      await loadWorkspaces();
      return ws;
    } catch (err: any) {
      if (err.message && err.message.includes('dialog_cancelled')) {
        return null; // Silence user cancellation
      }
      errorMsg.value = err.message || 'Folder selection failed or cancelled';
      return null;
    }
  };

  return {
    workspaces,
    isWorkspacesLoading,
    loadWorkspaces,
    selectWorkspaceDialog,
  };
}
