import { NextRequest, NextResponse } from "next/server"
import { SignJWT, jwtVerify } from "jose"
import { isValidToken, middleware } from "./middleware"

const TEST_SECRET = new TextEncoder().encode("test-secret-for-middleware")
const EXPIRED_SECRET = new TextEncoder().encode("expired-test-secret")

async function createExpiredToken(): Promise<string> {
  const token = await new SignJWT({ sub: "1", email: "test@test.com" })
    .setExpirationTime("0s")
    .setProtectedHeader({ alg: "HS256" })
    .sign(EXPIRED_SECRET)
  return token
}

async function createValidToken(): Promise<string> {
  const token = await new SignJWT({ sub: "1", email: "test@test.com" })
    .setExpirationTime("1h")
    .setProtectedHeader({ alg: "HS256" })
    .sign(TEST_SECRET)
  return token
}

describe("middleware", () => {
  const originalEnv = process.env.JWT_SECRET

  beforeAll(async () => {
    process.env.JWT_SECRET = "test-secret-for-middleware"
  })

  afterAll(() => {
    process.env.JWT_SECRET = originalEnv
  })

  describe("isValidToken", () => {
    it("returns true for valid token", async () => {
      const token = await createValidToken()
      const result = await isValidToken(token)
      expect(result).toBe(true)
    })

    it("returns false for expired token", async () => {
      const token = await createExpiredToken()
      await new Promise((resolve) => setTimeout(resolve, 100))
      const result = await isValidToken(token)
      expect(result).toBe(false)
    })

    it("returns false for malformed token", async () => {
      const result = await isValidToken("not-a-valid-jwt")
      expect(result).toBe(false)
    })

    it("returns false for empty token", async () => {
      const result = await isValidToken("")
      expect(result).toBe(false)
    })

    it("returns false when no JWT_SECRET is set", async () => {
      delete process.env.JWT_SECRET
      const token = await createValidToken()
      const result = await isValidToken(token)
      expect(result).toBe(false)
    })
  })

  describe("middleware redirect behavior", () => {
    it("redirects to /login when token is missing", async () => {
      const request = new NextRequest("http://localhost:3000/dashboard")
      const response = await middleware(request)

      expect(response.status).toBe(307)
      expect(response.headers.get("location")).toContain("/login")
    })

    it("redirects to /login when token is invalid", async () => {
      const request = new NextRequest("http://localhost:3000/dashboard", {
        headers: {
          cookie: "va_token=invalid-token",
        },
      })
      const response = await middleware(request)

      expect(response.status).toBe(307)
      expect(response.headers.get("location")).toContain("/login")

      const cookieHeader = response.headers.get("set-cookie")
      expect(cookieHeader).toContain("va_token=;")
    })

    it("allows requests for public routes", async () => {
      const request = new NextRequest("http://localhost:3000/login")
      const response = await middleware(request)

      expect(response.status).toBe(200)
    })

    it("allows next.js internals", async () => {
      const request = new NextRequest("http://localhost:3000/_next/static/chunk.js")
      const response = await middleware(request)

      expect(response.status).toBe(200)
    })
  })
})