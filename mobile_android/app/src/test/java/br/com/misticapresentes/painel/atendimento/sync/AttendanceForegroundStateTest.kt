package br.com.misticapresentes.painel.atendimento.sync

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AttendanceForegroundStateTest {

    @Before
    @After
    fun resetGlobalState() {
        AttendanceForegroundState.resetForTest()
    }

    @Test
    fun `no conversation is visible by default`() {
        assertFalse(AttendanceForegroundState.isConversationVisible(1L))
    }

    @Test
    fun `marks a conversation as visible`() {
        AttendanceForegroundState.setVisibleConversation(42L)
        assertTrue(AttendanceForegroundState.isConversationVisible(42L))
        assertFalse(AttendanceForegroundState.isConversationVisible(43L))
    }

    @Test
    fun `clearing a different conversation than the one visible does not clear it`() {
        AttendanceForegroundState.setVisibleConversation(42L)
        AttendanceForegroundState.clearVisibleConversation(99L)
        assertTrue(AttendanceForegroundState.isConversationVisible(42L))
    }

    @Test
    fun `clearing the currently visible conversation clears it`() {
        AttendanceForegroundState.setVisibleConversation(42L)
        AttendanceForegroundState.clearVisibleConversation(42L)
        assertFalse(AttendanceForegroundState.isConversationVisible(42L))
    }

    @Test
    fun `switching conversation A to conversation B never leaves both marked visible`() {
        AttendanceForegroundState.setVisibleConversation(1L)
        AttendanceForegroundState.setVisibleConversation(2L)
        assertFalse(AttendanceForegroundState.isConversationVisible(1L))
        assertTrue(AttendanceForegroundState.isConversationVisible(2L))
    }
}
