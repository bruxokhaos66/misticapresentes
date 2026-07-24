package br.com.misticapresentes.painel.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.atendimento.ui.detail.ConversationScreen
import br.com.misticapresentes.painel.atendimento.ui.list.AtendimentoListScreen
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.ui.common.LoadingScreen
import br.com.misticapresentes.painel.ui.common.NoConnectionScreen
import br.com.misticapresentes.painel.ui.common.SessionExpiredScreen
import br.com.misticapresentes.painel.ui.home.HomeScreen
import br.com.misticapresentes.painel.ui.login.LoginScreen
import br.com.misticapresentes.painel.ui.splash.SplashDestination
import br.com.misticapresentes.painel.ui.splash.SplashViewModel

@Composable
fun MisticaNavHost(
    container: AppContainer,
    onOpenLegacyPanel: () -> Unit,
    onEnterLegacyOnly: () -> Unit,
    navController: NavHostController = rememberNavController(),
) {
    val factory = remember(container) { MisticaViewModelFactory(container) }

    val authState by container.authRepository.authState.collectAsState()
    LaunchedEffect(authState) {
        if (authState is AuthState.SessionExpired && navController.currentDestination?.route != NavRoutes.SESSION_EXPIRED) {
            navController.navigate(NavRoutes.SESSION_EXPIRED) {
                popUpTo(0)
            }
        }
    }

    NavHost(navController = navController, startDestination = NavRoutes.SPLASH) {
        composable(NavRoutes.SPLASH) {
            val splashViewModel: SplashViewModel = androidx.lifecycle.viewmodel.compose.viewModel(factory = factory)
            val destination by splashViewModel.destination.collectAsState()

            LaunchedEffect(destination) {
                when (destination) {
                    SplashDestination.GoLogin -> navController.navigate(NavRoutes.LOGIN) { popUpTo(NavRoutes.SPLASH) { inclusive = true } }
                    SplashDestination.GoHome -> navController.navigate(NavRoutes.HOME) { popUpTo(NavRoutes.SPLASH) { inclusive = true } }
                    SplashDestination.GoNoConnection -> navController.navigate(NavRoutes.NO_CONNECTION) { popUpTo(NavRoutes.SPLASH) { inclusive = true } }
                    SplashDestination.GoLegacyOnly -> onEnterLegacyOnly()
                    SplashDestination.Loading -> Unit
                }
            }
            LoadingScreen()
        }

        composable(NavRoutes.LOGIN) {
            LoginScreen(
                factory = factory,
                onLoginSuccess = {
                    navController.navigate(NavRoutes.HOME) { popUpTo(NavRoutes.LOGIN) { inclusive = true } }
                },
            )
        }

        composable(NavRoutes.HOME) {
            HomeScreen(
                factory = factory,
                onOpenLegacyPanel = onOpenLegacyPanel,
                onOpenAtendimento = { navController.navigate(NavRoutes.ATENDIMENTO_LIST) },
                onLoggedOut = {
                    if (navController.currentDestination?.route == NavRoutes.HOME) {
                        navController.navigate(NavRoutes.LOGIN) { popUpTo(NavRoutes.HOME) { inclusive = true } }
                    }
                },
            )
        }

        composable(NavRoutes.ATENDIMENTO_LIST) {
            AtendimentoListScreen(
                factory = factory,
                onOpenConversation = { conversationId ->
                    navController.navigate(NavRoutes.atendimentoDetail(conversationId))
                },
                onBack = { navController.popBackStack() },
            )
        }

        composable(
            route = NavRoutes.ATENDIMENTO_DETAIL,
            arguments = listOf(navArgument("conversationId") { type = NavType.LongType }),
        ) { backStackEntry ->
            val conversationId = backStackEntry.arguments?.getLong("conversationId") ?: 0L
            ConversationScreen(
                container = container,
                conversationId = conversationId,
                onBack = { navController.popBackStack() },
            )
        }

        composable(NavRoutes.SESSION_EXPIRED) {
            SessionExpiredScreen(
                onGoToLogin = {
                    navController.navigate(NavRoutes.LOGIN) { popUpTo(0) }
                },
            )
        }

        composable(NavRoutes.NO_CONNECTION) {
            NoConnectionScreen(
                onRetry = {
                    navController.navigate(NavRoutes.SPLASH) { popUpTo(0) }
                },
            )
        }
    }
}
