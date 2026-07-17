import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './lib/supabaseClient.js'

const AuthContext = createContext({
  session: null,
  user: null,
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
})

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadSession = async () => {
      const { data, error } = await supabase.auth.getSession()
      if (error) {
        console.error('Failed to load auth session', error)
      }
      setSession(data?.session ?? null)
      setUser(data?.session?.user ?? null)
      setLoading(false)
    }

    loadSession()

   const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
  setSession(session ?? null)
  setUser(session?.user ?? null)
  setLoading(false)
})

    return () => {
      listener.subscription.unsubscribe()
    }
  }, [])

  const signIn = async ({ email, password }) => {
    return supabase.auth.signInWithPassword({ email, password })
  }

  const signUp = async ({ email, password, shopName, businessType }) => {
    return supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          shop_name: shopName,
          business_type: businessType,
        },
      },
    })
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ session, user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
