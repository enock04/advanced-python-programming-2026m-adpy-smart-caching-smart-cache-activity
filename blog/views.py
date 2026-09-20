# blog/views.py
#
# =============================================================================
#  SMART CACHE LAYER — GUIDED ACTIVITY
#  Advanced Python Programming | ALU BSE
# =============================================================================
#
#  This file contains three API views. Your job is to add caching to each one.
#  Read each TODO carefully — they build on each other.
#
#  Run the timing script first (docs/ACTIVITY.md → Level 1) to see
#  how slow the uncached responses are before you begin.
# =============================================================================

import time
import logging

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status

from .models import Post
from .serializers import PostSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LEVEL 2 — Shared Cache (Public Data)
# ---------------------------------------------------------------------------

class PostListView(APIView):
    """
    GET  /api/posts/       — Returns all published posts.
    POST /api/posts/       — Creates a new post (authenticated users only).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request):
        # STRETCH GOAL: fold query params into the cache key so that
        # /api/posts/?page=2 doesn't collide with /api/posts/.
        params = request.query_params.urlencode()
        cache_key = f"posts:list:published:{params}" if params else "posts:list:published"
        data = cache.get(cache_key)

        if data is None:
            posts = Post.objects.filter(status=Post.STATUS_PUBLISHED).select_related("author")
            serializer = PostSerializer(posts, many=True)
            data = serializer.data
            cache.set(cache_key, data, timeout=60)  # Cache for 60 seconds

        return Response(data)
    

    def post(self, request):
        # LEVEL 4: invalidate the list cache so the next GET reflects the new post.
        # Note: this only clears the no-params key. A query-aware GET (stretch
        # goal) can create other cached variants (e.g. "...?page=2") that this
        # single delete() won't touch.
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(author=request.user)
            cache.delete("posts:list:published")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# LEVEL 2 (continued) — Single Post Cache
# ---------------------------------------------------------------------------

class PostDetailView(APIView):
    """
    GET /api/posts/<post_id>/ — Returns a single published post.
    """

    permission_classes = [AllowAny]

    def get(self, request, post_id: int):
        cache_key = f"posts:detail:{post_id}"
        data = cache.get(cache_key)

        if data is None:
            try:
                post = Post.objects.select_related("author").get(
                    id=post_id, status=Post.STATUS_PUBLISHED
                )
            except Post.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = PostSerializer(post)
            data = serializer.data
            cache.set(cache_key, data, timeout=600)  # Cache for 600 seconds (10 minutes)

        return Response(data)


# ---------------------------------------------------------------------------
# LEVEL 3 — User-Isolated Cache (Personal Data)
# ---------------------------------------------------------------------------

class MyDraftsView(APIView):
    """
    GET /api/posts/my-drafts/ — Returns draft posts for the logged-in user only.

    !! SECURITY CRITICAL !!
    This endpoint returns private data. Every student must ensure
    that User A can never see User B's drafts under any circumstances.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # SECURITY: the cache key includes request.user.id so each user gets
        # their own cache entry. A generic key like "my-drafts" would be
        # shared by everyone — the first user to hit this endpoint would
        # populate the cache, and every other user would then be served
        # THAT user's drafts (a cross-account data leak) until it expired.
        cache_key = f"my-drafts:{request.user.id}"
        data = cache.get(cache_key)

        if data is None:
            drafts = Post.objects.filter(
                author=request.user,
                status=Post.STATUS_DRAFT
            ).select_related("author")

            serializer = PostSerializer(drafts, many=True)
            data = serializer.data
            cache.set(cache_key, data, timeout=120)  # 2 minutes — personal data expires quickly

        return Response(data)


# ---------------------------------------------------------------------------
# BONUS — Deliberately Broken View (Level 3 Bug-Spotting)
# ---------------------------------------------------------------------------

class BrokenDraftsView(APIView):
    """
    GET /api/posts/broken-drafts/

    This view has a critical security bug.
    Your task: read the code, find the bug, and explain it in the activity sheet.
    DO NOT fix the code here — write your answer in docs/ACTIVITY.md.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # !! BUG: find it, name it, explain the real-world impact !!
        data = cache.get("my-drafts")
        if data is None:
            drafts = Post.objects.filter(
                author=request.user,
                status=Post.STATUS_DRAFT
            ).select_related("author")
            serializer = PostSerializer(drafts, many=True)
            data = serializer.data
            cache.set("my-drafts", data, timeout=120)
        return Response(data)
