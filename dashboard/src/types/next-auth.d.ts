import "next-auth";

declare module 'next-auth' {
  interface User {
    isAdmin?: boolean;
    accessToken?: string;
    id?: string;
    authProvider?: string;
  }
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      isAdmin: boolean;
      accessToken: string;
      authProvider: string;
    }
  }
}
declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    isAdmin?: boolean;
    id?: string;
    authProvider?: string;
  }
}
