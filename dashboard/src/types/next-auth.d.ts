import "next-auth";

declare module 'next-auth' {
  interface User {
    isAdmin?: boolean;
    accessToken?: string;
  }
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      isAdmin: boolean;
      accessToken: string;
    }
  }
}
declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    isAdmin?: boolean;
    id?: string;
  }
}
