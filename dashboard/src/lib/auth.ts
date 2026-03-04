import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        console.log('Auth attempt:', credentials?.email);
        
        try {
          // Step 1: Login
          const loginRes = await fetch('/api/proxy/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: credentials?.email,
              password: credentials?.password
            })
          });
          
          console.log('Login response status:', loginRes.status);
          const loginData = await loginRes.json();
          console.log('Login response body:', JSON.stringify(loginData));
          
          if (!loginRes.ok) {
            console.log('Login failed - not ok');
            return null;
          }
          
          const accessToken = loginData.access_token;
          if (!accessToken) {
            console.log('No access token in response');
            return null;
          }
          
          // Step 2: Get user profile
          const meRes = await fetch('/api/proxy/api/auth/me', {
            headers: { 'Authorization': `Bearer ${accessToken}` }
          });
          
          console.log('Me response status:', meRes.status);
          const user = await meRes.json();
          console.log('Me response body:', JSON.stringify(user));
          
          if (!meRes.ok) {
            console.log('Me endpoint failed');
            return null;
          }
          
          return {
            id: user.id,
            email: user.email,
            name: user.name,
            isAdmin: user.is_admin,
            accessToken: accessToken
          };
          
        } catch (error) {
          console.error('Authorize exception:', error);
          return null;
        }
      },
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.isAdmin = user.isAdmin;
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.accessToken = token.accessToken as string;
      session.user.isAdmin = token.isAdmin as boolean;
      session.user.id = token.id as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
};
