import React, { useEffect, useRef } from "react";
import { useSearchParams, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/config/api";

/**
 * This page handles the final leg of the OAuth2 flow:
 * 1) Reads ?code= from the URL
 * 2) Sends it to /connections/oauth2/source/code
 * 3) Redirects back to /sync with a success or error flag
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
        navigate("/sync?connected=error", { replace: true });
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
        navigate("/sync?connected=success", { replace: true });
      } catch (err) {
        console.error('OAuth exchange error:', err);
        navigate("/sync?connected=error", { replace: true });
      }
    };

    doExchange();
  }, [searchParams, short_name, navigate]);

  // Nothing to render, user should not see anything
  return null;
} 