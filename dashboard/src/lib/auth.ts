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
          const loginRes = await fetch('http://localhost:8001/api/auth/login', {
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
          const meRes = await fetch('http://localhost:8001/api/auth/me', {
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
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
        },
      },
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      console.log('SignIn callback triggered:', { provider: account?.provider, user: user?.email });
      
      if (account?.provider === 'google') {
        try {
          console.log('Processing Google sign in...');
          
          const res = await fetch(
            'http://localhost:8001/api/auth/google/dashboard',
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                id_token: account.id_token 
              })
            }
          );
          
          console.log('Google auth backend response status:', res.status);
          
          if (!res.ok) {
            const errorText = await res.text();
            console.error('Google auth backend error:', res.status, errorText);
            return false;
          }
          
          const data = await res.json();
          console.log('Google auth response:', data);
          
          const accessToken = data.access_token;
          if (!accessToken) {
            console.error('No access token in Google auth response');
            return false;
          }
          
          // Fetch user profile
          const meRes = await fetch(
            'http://localhost:8001/api/auth/me',
            {
              headers: { 
                'Authorization': `Bearer ${accessToken}` 
              }
            }
          );
          
          console.log('Me endpoint response status:', meRes.status);
          
          if (!meRes.ok) {
            const errorText = await meRes.text();
            console.error('Failed to fetch user profile:', meRes.status, errorText);
            return false;
          }
          
          const profile = await meRes.json();
          console.log('User profile:', profile);
          
          // Attach to user object for jwt callback
          user.accessToken = accessToken;
          user.isAdmin = profile.is_admin;
          user.id = profile.id;
          user.authProvider = 'google';
          
          console.log('Google sign in successful for:', profile.email);
          return true;
        } catch (error) {
          console.error('Google sign in error:', error);
          return false;
        }
      }
      
      // For credentials provider, set authProvider
      if (account?.provider === 'credentials') {
        user.authProvider = 'local';
      }
      
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.isAdmin = user.isAdmin;
        token.id = user.id;
        token.authProvider = user.authProvider;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.accessToken = token.accessToken as string;
      session.user.isAdmin = token.isAdmin as boolean;
      session.user.id = token.id as string;
      session.user.authProvider = token.authProvider as string;
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
