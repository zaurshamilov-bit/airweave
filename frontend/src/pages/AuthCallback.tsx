import React, { useEffect, useRef } from "react";
import { useSearchParams, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";

/**
 * This page handles the final leg of the OAuth2 flow:
 * 1) Reads ?code= from the URL
 * 2) Sends it to /connections/oauth2/source/code
 * 3) Redirects back to the stored return URL or defaults to /sync/create with a success or error flag
 */
export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const { short_name } = useParams();
  const navigate = useNavigate();
  const exchangeAttempted = useRef(false);

  useEffect(() => {
    const doExchange = async () => {
      if (exchangeAttempted.current) return;
      exchangeAttempted.current = true;

      const code = searchParams.get("code");
      if (!code || !short_name) {
        // If query param missing or no short name, redirect back with error
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=error`, { replace: true });
        localStorage.removeItem("oauth_return_url");
        return;
      }

      try {
        const response = await apiClient.post(`/connections/oauth2/source/code`, {
          short_name,
          code,
        });
        if (!response.ok) {
          throw new Error("OAuth code exchange failed.");
        }

        // Get the return URL from localStorage or default to /sync/create
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=success`, { replace: true });
        localStorage.removeItem("oauth_return_url");
      } catch (err) {
        console.error('OAuth exchange error:', err);
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=error`, { replace: true });
        localStorage.removeItem("oauth_return_url");
      }
    };

    doExchange();
  }, [searchParams, short_name, navigate]);

  // Nothing to render, user should not see anything
  return null;
}
