declare namespace NodeJS {
  interface ProcessEnv {
    API_URL?: string;
    AUDIO_FILE_URL?: string;
  }
}

declare module 'process' {
  global {
    namespace NodeJS {
      interface ProcessEnv {
        API_URL?: string;
        AUDIO_FILE_URL?: string;
      }
    }
  }
}
