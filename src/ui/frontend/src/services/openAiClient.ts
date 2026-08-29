export interface OpenAiDiscoveryResult {
  success: boolean;
  modelName: string;
  modelDisplayName?: string;
  error?: string;
}

export class OpenAiClient {
  private static cachedModel: string | null = typeof window !== 'undefined' ? localStorage.getItem('openai_working_model') : null;

  /**
   * Dynamically query OpenAI API to discover active models and verify connection.
   */
  public static async discoverAndTestModel(apiKey: string): Promise<OpenAiDiscoveryResult> {
    const cleanKey = apiKey.trim();
    if (!cleanKey) {
      return { success: false, modelName: '', error: 'Lütfen önce geçerli bir OpenAI API anahtarı girin.' };
    }

    // 1. Try Models List endpoint
    try {
      const listRes = await fetch('https://api.openai.com/v1/models', {
        headers: {
          'Authorization': `Bearer ${cleanKey}`
        }
      });

      if (listRes.ok) {
        const listData = await listRes.json();
        const models: Array<{ id: string }> = listData.data || [];
        const modelIds = models.map(m => m.id);

        const preferredOrder = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o3-mini', 'gpt-3.5-turbo'];
        let bestModel = 'gpt-4o-mini';

        for (const pref of preferredOrder) {
          if (modelIds.includes(pref)) {
            bestModel = pref;
            break;
          }
        }

        const testRes = await this.callChatCompletion(cleanKey, bestModel, 'Test: Sadece "OK" yanıtı ver.');
        if (testRes.success) {
          this.cachedModel = bestModel;
          localStorage.setItem('openai_working_model', bestModel);
          return {
            success: true,
            modelName: bestModel,
            modelDisplayName: `OpenAI ${bestModel}`
          };
        }
      }
    } catch (e) {
      console.warn('OpenAI models list failed, testing direct candidate endpoints:', e);
    }

    // 2. Direct Fallback: Try candidates
    const candidateModels = ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'];
    let lastError = '';

    for (const model of candidateModels) {
      const res = await this.callChatCompletion(cleanKey, model, 'Test: Sadece "OK" yanıtı ver.');
      if (res.success) {
        this.cachedModel = model;
        localStorage.setItem('openai_working_model', model);
        return {
          success: true,
          modelName: model,
          modelDisplayName: `OpenAI ${model}`
        };
      } else {
        lastError = res.error || '';
      }
    }

    return {
      success: false,
      modelName: '',
      error: lastError || 'Kullanılabilir bir OpenAI modeli bulunamadı.'
    };
  }

  /**
   * Generate diagnostic response using OpenAI ChatGPT API.
   */
  public static async generateContent(
    apiKey: string,
    prompt: string,
    systemContext?: string
  ): Promise<{ success: boolean; text: string; modelUsed: string; error?: string }> {
    const cleanKey = apiKey.trim();
    if (!cleanKey) {
      return { success: false, text: '', modelUsed: '', error: 'OpenAI API anahtarı eksik.' };
    }

    let modelToUse = this.cachedModel || localStorage.getItem('openai_working_model') || 'gpt-4o-mini';
    const res = await this.callChatCompletion(cleanKey, modelToUse, prompt, systemContext);

    if (res.success && res.text.trim().length > 0) {
      return {
        success: true,
        text: res.text,
        modelUsed: modelToUse
      };
    }

    // Retry with dynamic discovery on failure
    const discovery = await this.discoverAndTestModel(cleanKey);
    if (discovery.success) {
      const retryRes = await this.callChatCompletion(cleanKey, discovery.modelName, prompt, systemContext);
      if (retryRes.success) {
        return {
          success: true,
          text: retryRes.text,
          modelUsed: discovery.modelName
        };
      }
    }

    return {
      success: false,
      text: '',
      modelUsed: modelToUse,
      error: res.error || 'OpenAI yanıt üretemedi.'
    };
  }

  private static async callChatCompletion(
    apiKey: string,
    model: string,
    userPrompt: string,
    systemPrompt?: string
  ): Promise<{ success: boolean; text: string; error?: string }> {
    try {
      const messages: Array<{ role: 'system' | 'user'; content: string }> = [];
      if (systemPrompt) {
        messages.push({ role: 'system', content: systemPrompt });
      }
      messages.push({ role: 'user', content: userPrompt });

      const res = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey.trim()}`
        },
        body: JSON.stringify({
          model,
          messages,
          temperature: 0.3,
          max_tokens: 1500
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const errMsg = errData.error?.message || `HTTP ${res.status} ${res.statusText}`;
        return { success: false, text: '', error: errMsg };
      }

      const data = await res.json();
      const text = data.choices?.[0]?.message?.content || '';
      return { success: true, text };
    } catch (err: any) {
      return { success: false, text: '', error: err.message || 'Ağ bağlantı hatası' };
    }
  }
}
